import urlparse
import os
import copy

import lxml.html as p

import processor.core.algorithm.transcoder_settings as settings
from processor.core.algorithm.utils import Utils
import transcode.utils.misc as misc
from processor.core.algorithm.classifiers import ClassifierBase
from transcode.utils.misc import remove_space, label_count

class Transcoder(object):
    @classmethod
    def _init_classifiers(cls, config, all_features):
        classifiers = {}
        for name, classifier_config in config["classifier_configs"].items():
            classifier = ClassifierBase.create_classifier(name, config["feature_extraction_parameters"], classifier_config, all_features)
            classifiers[name] = classifier

        return classifiers

    @classmethod
    def _override_config(cls, default_config, site_config):
        config = copy.deepcopy(default_config)
        Transcoder._merge_config(config, site_config)
        return config

    @classmethod
    def _merge_config(cls, dst_config, src_config):
        for key, value in src_config.items():
            if dst_config.has_key(key): #ignore keys not existed in dst config
                if isinstance(dst_config[key], dict) and isinstance(value, dict):
                    Transcoder._merge_config(dst_config[key], value)
                else:
                    dst_config[key] = value

    def __init__(self):
        self._all_features = {}
        self._default_config = settings.default_config
        self._default_classifiers = Transcoder._init_classifiers(self._default_config, self._all_features)

    def transcode(self, url, dom):
        if dom is None:
            return None

        #initialize
        self._all_features.clear() 

        #load per site config
        host = urlparse.urlparse(url).netloc
        if settings.site_configs.has_key(host):
            site_config = settings.site_configs[host]
            config = Transcoder._override_config(self._default_config, site_config)
            self._config = config
            if site_config.has_key("classifier_configs") or site_config.has_key("feature_extraction_parameters"):
                self._classifiers = Transcoder._init_classifiers(config, self._all_features)
            else:
                self._classifiers = self._default_classifiers
        else:
             self._config = self._default_config
             self._classifiers = self._default_classifiers

        #extract head node
        self._head_node = dom.find("head")
        if self._head_node is None:
            self._head_node = p.Element("head")
            dom.append(self._head_node)

        #recursively transcode
        self._transcode(dom)

        #post-process
        Utils.add_default_headers(dom)
        Utils.adjust_dom(dom)
   
        #list page classification
        self._classifiers["list_page_classifier"].add_extra("url", url)
        is_list = self._classifiers["list_page_classifier"].classify(dom)

        #special processes for details pages
        if not is_list:
            self._process_details_page(dom)
        return dom

    def _process_details_page(self, root):
        class_value = root.get('class','')
        if class_value is not None and class_value.find('dlinks') > -1:
            self._hide_node(root)
            return

        if not self._config["operation_switches"]["drop_scripts"] and self._config["operation_switches"]["drop_scripts_for_details"] and root.tag == "script":
            root.drop_tree()
            return

        for child in root.getchildren():
            self._process_details_page(child)

    def _transcode(self, node):
        #Validate node
        if not self._classifiers["valid_node_classifier"].classify(node):
            self._hide_node(node)
            self._all_features[node] = {"valid" : False}
            return False, None

        #Adjust layout to fit into mobile
        self._adjust_layout(node)

        #Extract features
        valid, features = self._extract_common_features(node)

        if not valid:
            self._all_features[node] = {"valid" : False}
            return False, None

        #recusive traverse children
        for child in node.getchildren():
            valid, child_features = self._transcode(child)
            if valid:
                features = Utils.aggregate_data(features, child_features)

        if (self._config["operation_switches"]["hide_empty_nodes"] or self._config["operation_switches"]["drop_empty_nodes"]) and Utils.is_empty_node(node, self._config["default_empty_tags"], self._config["invisible_tags"]):
            self._all_features[node] = {"valid" : False}
            if self._config["operation_switches"]["hide_empty_nodes"]:
                self._hide_node(node)
            else:
                if node.getparent() is not None:
                    print node.tag, p.tostring(node)
                    node.drop_tree()
            return False, None
        else:
            features["valid"] = True
            self._all_features[node] = features
            self._postprocess_node(node)
            node.set("data", str(features))
            return True, features

    def _hide_node(self, node):
        if isinstance(node, p.HtmlElement):
            style = node.get("style", "")
            if style is not None and len(style) > 0:
                style += " ; display: none !important;"
            else:
                style = "display: none !important;"
            node.set("style", style)

    def _adjust_layout(self, node):
        #filter invalid tag properties
        if self._config["operation_switches"]["filter_tag_properties"]:
            self._filter_tag_properties(node)

        #change tag properties
        if self._config["operation_switches"]["change_tag_properties"]:
            self._change_tag_properties(node)

        #change inline styles
        if self._config["operation_switches"]["change_inline_styles"]:
            self._change_inline_styles(node)

    def _filter_tag_properties(self, node):
        if self._config["filtered_tag_properties"].has_key(node.tag):
            properties = self._config["filtered_tag_properties"][node.tag]
            for name in properties:
                if name in node.attrib:
                    node.attrib.pop(name)
    
    def _change_tag_properties(self, node):
        for name, new_value in self._config["changed_tag_properties"].items():
            old_value = node.get(name, None)
            if old_value is not None and len(old_value) > 0:
                node.set(name, new_value)


    def _change_inline_styles(self, node):
        inline_style = node.get("style", "")
        if inline_style is not None and len(inline_style) > 0:
            inline_style = Utils.shrink_style(inline_style, self._config["filtered_css_properties"], self._config["changed_css_properties"])
            if inline_style is not None:
                node.set("style", inline_style)
            else:
                node.attrib.pop("style")

    def _extract_common_features(self, node):
        features = {"link_length" : 0, "link_length_bak" : 0, "link_count" : 0, "image_link_count" : 0, "short_link_count" : 0, "text_length" : 0, "large_text_count" : 0, "image_count" : 0}
        if node.tag == "a":
            if self._classifiers["valid_link_classifier"].classify(node):
                self._extract_link_features(node, features)
            else:
                self._hide_node(node)
                return False, None
        elif node.tag == "img":
            features["image_count"] = 1
            return True, features
        elif node.tag == "style":
            #move internal styles in <body> to <head>
            if self._config["operation_switches"]["move_internal_styles"]:
                self._move_internal_styles(node)
            return False, None
        elif node.tag == "script":
            if self._config["operation_switches"]["drop_scripts"]:
                node.drop_tree()
                return False, None
        elif node.tag in self._config["skipped_tags"]:
            return False, None

        features["text_length"] = label_count(remove_space(node.text.strip())) if node.text is not None else 0 + label_count(remove_space(node.tail.strip())) if node.tail is not None else 0

        if features["text_length"] >= self._config["large_text_threshold"]:
            features["large_text_count"] = 1

        return True, features

    def _move_internal_styles(self, node):
        parent_node = node.getparent()
        if not (parent_node is not None and parent_node.tag == "head"):
            node.drop_tree()
            self._head_node.append(node)

    def _extract_link_features(self, node, features):
        text = node.text_content().strip()
        text_length = Utils.label_count(text)
        image_link_count = len(node.findall('.//img'))
        features["link_length"] = text_length
        features["image_link_count"] = image_link_count
        features["short_link_count"] = 1 if text_length <= self._config["min_link_length"] else 0
        features["link_count"] = 1
        features["link_length_bak"] = text_length #TODO: not sure how is this used


    def _postprocess_node(self, node):
        if self._config["operation_switches"]["reorder_nodes"]:
            self._reorder_nodes(node)

        if self._config["operation_switches"]["classify_nodes"]:
            self._classify_nodes(node)
        if self._config["operation_switches"]["mark_link_containers"] and node.tag in self._config["link_containers"]:
            data = self._mark_link_containers(node)

    def _classify_nodes(self, node):
        """
        classification result: link, navigation, spam
        """

        is_link_node = self._classifiers["link_node_classifier"].classify(node)
        if is_link_node:
            Utils.add_class(node, 'dlinks')

    def _reorder_nodes(self, node):
       #valid reorder parent
        if self._classifiers["reorder_parent_classifier"].classify(node):
            child_features = []
            for child in node.getchildren():
                #valid reorder child
                if self._all_features[child]["valid"] and self._classifiers["reorder_child_classifier"].classify(child):
                    #calculate rating
                    rating = self._classifiers["reorder_rating_classifier"].classify(child)
                    child_features.append({"node" : child, "rating": rating})
                else:
                    return False

            #reorder
            for child in sorted(child_features, key = lambda child : child["rating"]):
                child["node"].drop_tree() #can't hide
                node.append(child["node"])

            return True
        else:
            return False

    def _replace_child_class(self, node, class_name, new_class_name=''):
        for child in node.find_class(class_name):
            class_str = child.get('class', '').replace(class_name, new_class_name)
            if class_str:
                child.set('class', class_str)
            else:
                child.attrib.pop('class')

    def _shrink_nav_node(self, node):
        for anchor in node.findall('.//a'):
            anchor.tail = None
    
    def _mark_link_containers(self, node):
        features = self._all_features[node]
        if features["text_length"] > 0 and float(features['link_length'])/features["text_length"] > self._config["link_threshold"]:
            if float(features['short_link_count']) / features['link_count'] > self._config["short_link_threshold"]:
                self._shrink_nav_node(node)
                if features['short_link_count'] == 1:
                    self._replace_child_class(node, 'dnav')
                    Utils.add_class(node, 'dnav')
                elif features['short_link_count'] > 3:
                    self._replace_child_class(node, 'dnavb', new_class_name='dnavg')
                    Utils.add_class(node, 'dnavb')
                else:
                    self._replace_child_class(node, 'dnavg')
                    Utils.add_class(node, 'dnavg')
            else:
                Utils.add_class(node, 'dlst')
                #clear all link data since dolphinList is not recursive class
                #features['link_count'] = 0
                #features['short_link_count'] = 0
                #features['link_length'] = 0
