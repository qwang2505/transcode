default_config = {

    "default_empty_tags" : ['frame','img', 'base', 'br', 'link', 'body', 'head', "input"],

    "large_text_threshold" : 80,
    "link_threshold" : 0.5,
    "short_link_threshold" : 0.8,

    "link_containers" : ['div','p', 'h1','h2','h3','h4','h5','h6',"ul", "li"],

    "min_link_length" : 7,

    "filtered_tag_properties" : {
        "table" : ["cellspacing", "cellpadding"],
    },

    "changed_tag_properties" : {
        "width" : "auto",
    },

    "filtered_css_properties" : ["width", "float", "position", "padding", "margin"],

    "changed_css_properties" : {
    },

    #skipped tags: non visible, non-text,
    "skipped_tags" : ["noscript", "noframes", "script", "style", "param", "object", "applet", "meta", "title"],
    "invisible_tags":["noscript", "noframes", "script", "style", "param",],

    "operation_switches" : {
        "move_internal_styles" : True,
        "change_inline_styles" : True,
        "change_tag_properties" : True,
        "filter_tag_properties" : True,
        "reorder_nodes" : True,
        "classify_nodes" : True,
        "hide_empty_nodes" : True,
        "drop_empty_nodes" : False,
        "mark_link_containers" : True,
        "drop_scripts" : False,
        "drop_scripts_for_details" : True,
    },

    "feature_extraction_parameters" : {
        "white_tags" : [],
        "black_tags" : ["iframe", "embed"],
        "removed_names" : ['bar', 'foot', 'friend', 'slide', 'calendar', "header", "sidebar"],
        "removed_words" : ['ad'],
        "large_text_count_threshold" : 2,
        "non_link_text_threshold" : 600,
        "url_filename_blacklist" : ["forum.", "list", "default.", "index."],
        "min_child_count" : 1,
        "max_child_count" : 4,
        "valid_reorder_parent_tags" : ["div"],
        "valid_reorder_child_tags" : ["div"],
        "min_text_length" : 500,
        "min_image_count" : 2,
        "link_ratio_threshold" : 0.5,
        "non_link_length_threshold" : 20,
        "filtered_url_domains" : ['allyes.com', 'ad-plus.cn'],
    },

    "classifier_configs" : {
        "valid_node_classifier" : {
            "type" : "BooleanClassifier",
            "features" : ["is_elem", "not_in_blacklist", "not_hidden", "not_filtered_by_name", "not_filtered_by_word"], #must be list type to make sure order
        },

        "list_page_classifier" : {
            "type" : "SvmClassifier",
            "model_filepath" : "./processor/processor/core/algorithm/classifier/list_page_classifier.svm",
            "features" : ["link_text_ratio", "url_is_filename", "non_link_text_length_high", "large_text_count_high"],
        },

        "reorder_parent_classifier" : {
            "type" : "BooleanClassifier",
            "features" : ["valid_reorder_parent_tag", "node_not_empty", "child_count_in_range",],
        },

        "reorder_child_classifier" :  {
            "type" : "BooleanClassifier",
            "features" : ["valid_reorder_child_tag", "large_content",],
        },

        "reorder_rating_classifier" :  {
            "type" : "LinearClassifier",
            "linear" : {"image_text_ratio" : 1},
        },

        "link_node_classifier" : {
            "type" : "BooleanClassifier",
            "features" : ["link_ratio_high", "non_link_length_low",],
        },

        "valid_link_classifier" : {
            "type" : "BooleanClassifier",
            "features" : ["link_not_nofollow", "link_not_empty", "link_not_filtered",],
        },
    },
}

site_configs = {
    "news.sina.com.cn" : {},
}
