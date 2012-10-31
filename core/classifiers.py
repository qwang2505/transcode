import urlparse
import os

import lxml.html as p

import processor.core.algorithm.classifier.svmutil as svmutil
from processor.core.algorithm.utils import Utils
import transcode.utils.misc as misc

class FeatureExtractor(object):
    def __init__(self, parameters, all_features):
        self._parameters = parameters
        self._features = all_features
        self._extra = {}

    def _is_not_filtered_by_name(self, node):
        class_value = node.get("class", "")
        id_value = node.get("id", "")
        if class_value is not None and len(class_value) > 0 and len(filter(lambda item : class_value.find(item) != -1, self._parameters["removed_names"])) > 0:
            return False

        if id_value is not None and len(id_value) > 0 and len(filter(lambda item : id_value.find(item) != -1, self._parameters["removed_names"])) > 0:
            return False

        return True

    def _is_not_filtered_by_word(self, node):
        class_value = node.get("class", "")
        id_value = node.get("id", "")
        if self._contains_word(class_value):
            return False
        if self._contains_word(id_value):
            return False

        return True

    def _contains_word(self, text):
        if text is not None and len(text) > 0:
            words = ''.join(map(lambda ch : ch if ch.isalpha() or ch.isdigit() else ' ', text))
            words = words.split()
            for word in words:
                if len(filter(lambda w : w == word or w.startswith(word), self._parameters["removed_words"])) > 0:
                    return True

        return False

    def _not_dynamic_node(self, node):
        tag_count = 0
        script_count = 0
        for child in node.getchildren():
            if isinstance(node, p.HtmlElement):
                tag_count += 1
                if node.tag == "script":
                    script_count += 1

        return script_count == 0 or tag_count != script_count

    def _link_not_empty(self, node):
        href = node.get('href', '')
        return href is not None and len(href) > 0

    def _link_not_filtered(self, node):
        #check if url domain is in filtered list
        href = node.get('href', '')
        parsed_result = urlparse.urlparse(href)
        if len(parsed_result.netloc) > 0 and len(filter(lambda domain : parsed_result.netloc.find(domain) != -1, self._parameters["filtered_url_domains"])) > 0:
            return False
        return True

    def _is_url_filename(self, url):
        parse_result = urlparse.urlparse(url)
        filename = os.path.basename(parse_result.path)
        is_filename = len(filename) > 0
        if is_filename and misc.find_list(filename, self._parameters["url_filename_blacklist"]):
            is_filename = False

        return is_filename

    #Notes: make sure the dependent features should be calculated before use
    _extractors = {
        #ValidNodeClassifier
        "is_elem" : lambda self, node : isinstance(node, p.HtmlElement),
        "in_whitelist":  lambda self, node : node.tag in self._parameters["white_tags"],
        "not_in_blacklist": lambda self, node : not node.tag in self._parameters["black_tags"],
        "not_hidden": lambda self, node : not Utils.is_hidden_node(node),
        "not_filtered_by_name": _is_not_filtered_by_name,
        "not_dynamic_node" : _not_dynamic_node,
        "not_filtered_by_word" : _is_not_filtered_by_word,

        #ReorderParentClassifier
        "valid_reorder_parent_tag" : lambda self, node : node.tag in self._parameters["valid_reorder_parent_tags"],
        "node_not_empty" : lambda self, node : len(node.getchildren()) > 0 or self._features[node]["text_length"] > 0,
        "child_count_in_range" : lambda self, node :  len(node.getchildren()) > self._parameters["min_child_count"] and len(node.getchildren()) < self._parameters["max_child_count"],

        #ReorderChildClassifier
        "valid_reorder_child_tag" : lambda self, node : node.tag in self._parameters["valid_reorder_child_tags"],
        "large_content" : lambda self, node : self._features[node]["text_length"] > self._parameters["min_text_length"] or self._features[node]["image_count"] > self._parameters["min_image_count"],

        #ReorderRatingClassifier
        "image_text_ratio" : lambda self, node : 1.0 * self._features[node]["image_count"] / self._features[node]["text_length"] if self._features[node]["text_length"] != 0 else 1, #TODO why 1 here

        #LinkNodeClassifier
        "link_ratio_high" : lambda self, node : (1.0 * self._features[node]["link_length"] / self._features[node]["text_length"] if self._features[node]["text_length"] != 0 else 0) > self._parameters["link_ratio_threshold"],
        "non_link_length_low" : lambda self, node : self._features[node]["text_length"] - self._features[node]["link_length"] < self._parameters["non_link_length_threshold"],

        #ListPageClassifier
        "link_text_ratio" : lambda self, node : 1.0 * self._features[node]["link_length"] / self._features[node]["text_length"] if self._features[node]["text_length"] != 0 else 0,
        "url_is_filename": lambda self, node : self._is_url_filename(self._extra["url"]),
        "non_link_text_length_high" : lambda self, node: self._features[node]["text_length"] - self._features[node]["link_length"] >= self._parameters["non_link_text_threshold"],
        "large_text_count_high" : lambda self, node : self._features[node]["large_text_count"] >= self._parameters["large_text_count_threshold"],

        #ValidLinkClassifier
        "link_not_nofollow" : lambda self, node : node.get("rel", "") != "nofollow",
        "link_not_empty" : _link_not_empty,
        "link_not_filtered" : _link_not_filtered,
    }


    def add_extra(self, key, value):
        self._extra[key] = value

    def extract_feature(self, node, feature_name):
        if FeatureExtractor._extractors.has_key(feature_name):
            extractor = FeatureExtractor._extractors[feature_name]
            return extractor(self, node)
        else:
            raise Exception("feature %s not found" % feature_name)

    def extract_features(self, node, feature_names):
        features = {}
        for feature_name in feature_names:
            if self._features.has_key(feature_name):
                features[feature_name] = self._features[feature_name]
            else:
                features[feature_name] = self.extract_feature(node, feature_name)

        try:
            node.set("features", str(node.get("features", "")) + " " + str(features))
        except:
            pass
        return features

class ClassifierBase(object):
    @classmethod
    def create_classifier(cls, classifier_name, feature_extraction_parameters, classifier_config, all_features):
        classifier_type = classifier_config["type"]
        if classifier_type == "BooleanClassifier":
            return BooleanClassifier(classifier_name, feature_extraction_parameters, classifier_config, all_features)
        elif classifier_type == "LinearClassifier":
            return LinearClassifier(classifier_name, feature_extraction_parameters, classifier_config, all_features)
        elif classifier_type == "SvmClassifier":
            return SvmClassifier(classifier_name, feature_extraction_parameters, classifier_config, all_features)
        else:
            raise Exception("unsupported classifier_type %s" % type)

    def __init__(self, name, parameters, config, all_features):
        self._classifier_name = name
        self._parameters = parameters
        self._config = config
        self._all_features = all_features
        self._feature_extractor = FeatureExtractor(parameters, all_features)
        self._initialize()

    def _initialize(self):
        pass

    def _extract_features(self, node):
        return self._feature_extractor.extract_features(node, self._config["features"])

    def _classify(self, features):
        pass

    def add_extra(self, key, value):
        self._feature_extractor.add_extra(key, value)

    def classify(self, node):
        features = self._extract_features(node)
        return self._classify(features)

class BooleanClassifier(ClassifierBase):

    """
    condition: atom and atom and atom ...
    atom: not atom_enabled or atom_expr
    #atom_expr: value op data
    #op: eq, lt, gt, ne
    """

    @classmethod
    def _execute_model(cls, features, funcs, config, parameters):
        """
        funcs is a func dict, each func is name, bool func(features, parameters)
        """
        for name in config["features"]:
            if features.has_key(name):
                success = features[name] != 0
            elif funcs is not None and funcs.has_key(name): #one switch can be optional
                func = funcs[name]
                success = func(features, parameters)
            else:
                raise Exception("unsupported name %s" % name)

            if not success:
                return False

        return True

    def _get_model(self):
        pass

    def _classify(self, features):
        model = self._get_model()
        return BooleanClassifier._execute_model(features, model, self._config, self._parameters)

class LinearClassifier(ClassifierBase):
    def _extract_features(self, node):
        return self._feature_extractor.extract_features(node, self._config["linear"].keys())

    def _classify(self, features):
        score = 0
        for name, weight in self._config["linear"].items():
            if features.has_key(name):
                score += features[name] * weight
            else:
                raise Exception("feature %s not found" % name)
        
        return score

class SvmClassifier(ClassifierBase):
    def _initialize(self):
        self._svm_model = svmutil.svm_load_model(self._config["model_filepath"])

    def _classify(self, features):
        self._normalize_features(features)

        feature_vector = []
        for feature_name in self._config["features"]:
            if features.has_key(feature_name):
                feature_vector.append(features[feature_name])
            else:
                raise Exception("required feature not found %s" % feature_name)

        labels, _, _ = svmutil.svm_predict([0], [feature_vector], self._svm_model)
        return labels[0] == 1.0

    def _normalize_features(self, features):
        for name in features:
            if isinstance(features[name], bool):
                features[name] = 1 if features[name] else 0
