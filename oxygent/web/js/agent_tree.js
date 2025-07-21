!(function(name, factory) {
    try {
        if ($) {}
    } catch (error) {
        console.warn(error + "【本项目需要依赖jquery库】");
        return
    }
    if (typeof exports === 'object') {
        module.exports = factory();
    } else if (typeof define === 'function' && define.amd) {
        define(factory);
    } else {
        window[name] = factory();
    }

})("HOkrTree", function() {
    var isdrop = true;
    var namespace = "HOkrTree";
    var dataArray = [];
    var cssNameSpace = "";
    var tagCalback = null;
    var itemCallback = null;

    function buildNode(data) {
        /**js-core**/
        var template = function(data, root, tag_index, z_type) {
            var s = "",
                len = data.length;
            $.each(data, function(index, item) {
                var tag = "",
                    zr = "",
                    tagIndex = 0;
                /*提前 处理tag标记*/
                item.children && $.each(item.children, function(index, item1) {
                    if (item1.type && item1.type == "tag") {
                        tag = `<div class="tagBox">
                          <div class="tagNode">
                            <div class="tag-line">
                              <div class="taglineDown"></div>
                            </div>
                            <div class="tag-node">
                              ${tagCalback ? tagCalback(item1) : ''}
                            </div>
                          </div>
                        </div>`;

                        if (item.children.length > 1 && index == 0) {
                            tagIndex = 1;
                            zr = "top";
                        } else {
                            (item.children.length - 1 == index) && (tagIndex = item.children.length - 2, zr = "bottom");

                        }
                    }
                })
                if (item.type && item.type == "tag") return;

                s += `
                  <div class="node-cell">
                    ${
                      !item.children || item.children.length === 0
                        ? `
                          <div class="node">
                            ${itemCallback?.(item) || ''}
                          </div>
                          <div class="node-lines">
                            <div class="line-top${(index === 0 || (z_type === 'top' && index === tag_index)) ? ' first' : ''}"></div>
                            <div class="line-bottom${(index === len - 1 || (z_type === 'bottom' && index === tag_index)) ? ' last' : ''}"></div>
                          </div>
                        `
                        : `
                          <div class="node-parent">
                            <div class="node">
                                ${itemCallback?.(item) || ''}
                                
                            </div>
                            <div class="node-lines" ${root ? 'style="display:none"' : ''}>
                              <div class="line-top${(index === 0 || (z_type === 'top' && index === tag_index)) ? ' first' : ''}"></div>
                              <div class="line-bottom${(index === len - 1 || (z_type === 'bottom' && index === tag_index)) ? ' last' : ''}"></div>
                            </div>
                          </div>
                          ${tag || ''}
                          <div class="line">
                            <div class="line-right"></div>
                          </div>
                          <div class="node-childrens">
                            ${template(item.children, false, tagIndex, zr)}
                          </div>
                        `
                    }
                  </div>
                `;
            });
            return s;
        };
        return template(data, true);
    }


    function renderLayout() {
        $(cssNameSpace).html(buildNode(dataArray));
        $(cssNameSpace + ' .tagNode').each(function(index, item) {
            $(item).css({
                height: $(item).height() * 2 + 100 + "px"
            })
        })
    }


    function initEvent() {
        $(cssNameSpace + " .expandIcon").on('click', function() {

            if ($(this).text() == "+") {
                $(this).text("-");
            } else {
                $(this).text("+");
            }
            $(this).parent().parent().parent().nextAll().toggle(120);
        });
    }

    function init() {
        renderLayout();
        initEvent();
    }
    $.fn[namespace] = function(options) {
        cssNameSpace = this.selector;
        var defaults = {
            version: "1.0",
            isdrop: true,
            data: [],
        },
        opts = $.extend({}, defaults, options);

        this.addClass(namespace);
        dataArray = opts.data instanceof Array && opts.data;
        typeof opts.itemTemplate == 'function' && (itemCallback = opts.itemTemplate);
        typeof opts.tagTemplate == 'function' && (tagCalback = opts.tagTemplate);
        typeof opts.isdrop == 'boolean' && (isdrop = opts.isdrop);
        init();
        return opts;
    }
})