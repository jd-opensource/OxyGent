/**
 * @description 去重
 * @param {*} data
 * @returns
 */
function unionName(data) {
    return [...new Set(data)]
}

/**
 * @description 数组转map
 * @param {*} nodes
 * @returns
 */
function arrayToMap(nodes) {
    const nodeMap = []
    for (const node of nodes) {
        nodeMap[node.node_id] = {...node, children: []};
    }
    return nodeMap;
}

/**
 * @description 构建树结构
 * @param {*} nodes
 * @returns
 */
function buildTree(nodes) {
    console.log('nodes', nodes);
    const nodeMap = {};
    const tree = [];

    // 首先将所有节点存入映射表
    for (const node of nodes) {
        nodeMap[node.node_id] = {...node, children: []};
    }

    // 然后构建树结构
    for (const node of nodes) {
        if (node.father_node_id === '') {
            tree.push(nodeMap[node.node_id]);
        } else {
            const parent = nodeMap[node.father_node_id];
            if (parent) {
                parent.children.push(nodeMap[node.node_id]);
            }
        }
    }

    return tree;
}

/**
 * @description 获取变量类型
 * @param {*} value
 * @returns
 */
function getType(value) {
    // 处理 null 的特殊情况
    if (value === null) {
        return 'null';
    }

    // 处理基本类型
    const type = typeof value;
    if (type !== 'object') {
        return type;
    }

    // 处理对象类型
    const toString = Object.prototype.toString.call(value);
    const typeString = toString.slice(8, -1).toLowerCase();

    // 特殊处理一些类型
    if (typeString === 'object') {
        if (value.constructor) {
            return value.constructor.name.toLowerCase();
        }
    }

    return typeString;
}

/**
 * @description 生成脚本id
 * @returns
 */
function generateScriptId() {
    const date = new Date();
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const h = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    const s = String(date.getSeconds()).padStart(2, '0');
    return `repro_script_${y}${m}${d}${h}${min}${s}`;
}


function getTextWidth(text) {
    var tempDiv = $('<div>').css({
        position: 'absolute',
        float: 'left',
        whiteSpace: 'nowrap',
        visibility: 'hidden',
        fontSize: $('#message_input').css('font-size') // 或者其他样式属性
    }).text(text);
    $('body').append(tempDiv);
    var width = tempDiv.width();
    tempDiv.remove(); // 移除临时元素，清理DOM
    return width;
}
