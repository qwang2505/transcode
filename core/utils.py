import copy
import re

import lxml.html as p
import processor.core.algorithm.classifier.svmutil as svmutil

from transcode.utils.misc import remove_space

class Utils(object):

    _list_page_classifier = None

    @classmethod
    def is_hidden_node(cls, node):
        ''' Check if a node is hidden in html page
        '''
        style_list = node.get('style', None)
        if style_list:
            for p in style_list.split(';'):
                tokens = p.split(':')
                if len(tokens) >= 2 and tokens[0].strip().lower() == 'display' and tokens[1].strip().lower() == 'none':
                    return True
        return False

    @classmethod
    def is_empty_node(cls, node, default_empty_tags, invisible_tags):
        ''' Check if a node is empty
        '''
        if node.tag not in default_empty_tags:
            text_length = len(remove_space(node.text_content()))
            #children_length = len(node.getchildren())
            children_length = len(filter(lambda child : child not in invisible_tags, node.getchildren()))
            return children_length == 0 and text_length == 0
        return False

    @classmethod
    def label_count(cls, text):
        ''' calculate count of such labels: Chinese characters, English words, number and punctuations
        '''
        if not isinstance(text, unicode):
            return len(text)
        else:
            count = 0
            fragments = text.split()
            for fragment in fragments:
                has_charactor_list = False
                for uchar in fragment:
                    if (uchar >= u'\u0030' and uchar<=u'\u0039') \
                        or (uchar >= u'\u0041' and uchar<=u'\u005a') \
                        or (uchar >= u'\u0061' and uchar<=u'\u007a'):
                        has_charactor_list = True
                    else:
                        if has_charactor_list:
                            count += 1
                            has_charactor_list = False
                        count += 1
                if has_charactor_list:
                    count += 1
            return count

    @classmethod
    def aggregate_data(cls, data, sub_data):
        if not (data and sub_data):
            return data or sub_data
        for key, value in sub_data.items():
            if key in data:
                data[key] += value
            else:
                data[key] = value
        return data
 
    @classmethod
    def add_class(cls, node, classname):
        node.set('class', ' '.join((node.get('class', ''), classname)))
    

    @classmethod
    def add_default_headers(cls, node):
        head = node.head
        if head is None:
            head = p.Element("head")
            node.append(head)

        link_node = p.Element("link")
        link_node.attrib["href"] = "./dolphinT.css"
        link_node.attrib["rel"] = "stylesheet"
        head.append(link_node)
        script_node = p.Element("script")
        script_node.attrib["src"] = "http://test1.dolphin-browser.com/yfhe/dolphinT.js"
        script_node.attrib["charset"] = "utf-8"
        head.append(script_node)

    @classmethod
    def adjust_dom(cls, root):
        ''' adjust paged dom. 
            1. add id for navigationBar
            2. generate shadow node of navigationBar
        '''
        i = 1
        for child in root.find_class('dnavb'):
            child.set('id', "%s_%d" % ('dnavb', i))
            child.set('class', child.get('class', '') + ' dnavh')
            shadow = p.fragment_fromstring('<div class="dnavg show"></div>')
            child.insert(0, shadow)
            for anchor in child.findall('.//a')[:3]:
                shadow.append(copy.deepcopy(anchor))
            shadow.append(p.fragment_fromstring("<a>...</a>"))
            i += 1

    @classmethod
    def shrink_style(cls, style_str, filtered_css_properties, changed_css_properties):
        if not style_str:
            return None
        properties = {}
        for p in style_str.split(';'):
            if p.strip():
                token = p.split(':')
                if len(token) > 1:
                    properties[token[0].strip()] = token[1].strip()
        return Utils._shrink_properties(properties, filtered_css_properties, changed_css_properties)

    @classmethod
    def _shrink_properties(cls, properties, filtered_css_properties, changed_css_properties):
        """
        removes !important and filtered_css_properties
        """

        result = {}
        for name in properties:
            if not name in filtered_css_properties:
                if changed_css_properties.has_key(name):
                    value = changed_css_properties[name]
                else:
                    value = properties[name].replace('!important','')

                result[name] = value
        if len(result) > 0:
            properties = ';'.join(map(lambda i: '%s:%s' % i, result.items()))
            return '{'+properties+'}'
        else:
            return None
