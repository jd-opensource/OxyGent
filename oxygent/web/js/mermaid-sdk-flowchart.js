

function convertAgentFlowToMermaidWithSubgraphs(nodes) {
        // 节点类型到样式的映射
        const nodeTypeStyles = {
            'user': 'fill:#6f6,stroke:#333',
            'agent': 'fill:#bbf,stroke:#333',
            'llm': 'fill:#f96,stroke:#333',
            'tool': 'fill:#f9f,stroke:#333',
            'output': 'fill:#fff,stroke:#333,stroke-width:2px',
            'subgraph': 'fill:#eee,stroke:#666,stroke-dasharray:5 5'
        };

        // 存储所有元素
        const elements = {
            nodeDefinitions: [],
            connections: [],
            styleDefinitions: [],
            subgraphs: {}
        };

        // 存储已处理的节点ID
        const processedNodes = new Set();

        // 找到根节点
        const rootNode = nodes.find(node => !node.father_node_id && node.caller === 'user') || nodes[0];
        if (!rootNode) throw new Error('找不到根节点');

        // 构建子图层级关系
        function buildSubgraphHierarchy() {
            const hierarchy = {};

            nodes.forEach(node => {
                if (node.subgraph && !hierarchy[node.subgraph]) {
                    hierarchy[node.subgraph] = {
                        parent: getParentSubgraph(node.subgraph, nodes),
                        nodes: []
                    };
                }

                if (node.subgraph) {
                    hierarchy[node.subgraph].nodes.push(node.node_id);
                }
            });

            return hierarchy;
        }

        // 获取父级子图
        function getParentSubgraph(subgraph, nodes) {
            const parts = subgraph.split('.');
            if (parts.length > 1) {
                return parts.slice(0, -1).join('.');
            }
            return null;
        }

        // 处理节点
        function processNode(node, currentSubgraph = null) {
            if (processedNodes.has(node.node_id)) return;
            processedNodes.add(node.node_id);

            // 确定节点显示属性
            const {displayName, nodeType} = getNodeDisplayInfo(node);

            // 如果是输出节点特殊处理
            if (node.node_id === nodes[nodes.length - 1].node_id) {
                const outputContent = formatOutputContent(node.output);
                elements.nodeDefinitions.push(`${node.node_id}["${outputContent}"]`);
                elements.styleDefinitions.push(`class ${node.node_id} output`);
                return;
            }

            // 添加节点定义
            elements.nodeDefinitions.push(`${node.node_id}["${displayName}"]`);
            elements.styleDefinitions.push(`class ${node.node_id} ${nodeType}`);

            // 处理子节点
            processChildNodes(node, currentSubgraph);

            // 处理后续节点
            processPostNodes(node, currentSubgraph);
        }

        // 获取节点显示信息
        function getNodeDisplayInfo(node) {
            let displayName, nodeType;

            if (node.node_type === 'agent') {
                displayName = node.callee || node.node_id;
                nodeType = 'agent';
            } else if (node.node_type === 'llm') {
                displayName = node.callee || 'qwen32b';
                nodeType = 'llm';
            } else if (node.node_type === 'tool') {
                displayName = node.callee || 'tool';
                nodeType = 'tool';
            } else {
                displayName = node.node_id;
                nodeType = 'agent';
            }

            // 缩短过长的显示名称
            displayName = displayName.length > 15 ?
                `${displayName.substring(0, 12)}...` : displayName;

            return {displayName, nodeType};
        }

        // 格式化输出内容
        function formatOutputContent(output) {
            if (!output) return '输出结果';

            // 提取关键信息或简化输出
            const maxLength = 50;
            if (output.length > maxLength) {
                const firstLine = output.split('\n')[0];
                return `${firstLine.substring(0, maxLength)}...`;
            }
            return output.replace(/\n/g, '<br/>');
        }

        // 处理子节点
        function processChildNodes(node, currentSubgraph) {
            if (node.child_node_ids && node.child_node_ids.length > 0) {
                node.child_node_ids.forEach(childId => {
                    const childNode = nodes.find(n => n.node_id === childId);
                    if (childNode) {
                        // 检查子节点是否属于不同子图
                        if (childNode.subgraph !== currentSubgraph) {
                            // 如果子节点有子图而当前没有，先创建子图连接
                            if (childNode.subgraph && !currentSubgraph) {
                                elements.connections.push(`${node.node_id} --> ${childNode.subgraph}`);
                            }
                            // 如果当前在子图中而子节点不在，连接到子图出口
                            else if (currentSubgraph && !childNode.subgraph) {
                                elements.connections.push(`${currentSubgraph}_exit --> ${childNode.node_id}`);
                            }
                            // 其他情况直接连接
                            else {
                                elements.connections.push(`${node.node_id} --> ${childNode.node_id}`);
                            }
                        } else {
                            elements.connections.push(`${node.node_id} --> ${childNode.node_id}`);
                        }

                        processNode(childNode, childNode.subgraph || currentSubgraph);
                    }
                });
            }
        }

        // 处理后续节点
        function processPostNodes(node, currentSubgraph) {
            if (node.post_node_ids && node.post_node_ids.length > 0) {
                node.post_node_ids.forEach(postId => {
                    const postNode = nodes.find(n => n.node_id === postId);
                    if (postNode) {
                        // 同子图内连接
                        if (postNode.subgraph === currentSubgraph) {
                            elements.connections.push(`${node.node_id} --> ${postNode.node_id}`);
                        }
                        // 跨子图连接
                        else if (currentSubgraph && !postNode.subgraph) {
                            elements.connections.push(`${currentSubgraph}_exit --> ${postNode.node_id}`);
                        }
                        // 其他情况
                        else {
                            elements.connections.push(`${node.node_id} --> ${postNode.node_id}`);
                        }

                        processNode(postNode, postNode.subgraph || currentSubgraph);
                    }
                });
            }
        }

        // 构建子图结构
        function buildSubgraphs() {
            const hierarchy = buildSubgraphHierarchy();

            // 按层级构建子图
            Object.entries(hierarchy).forEach(([subgraphName, {nodes: subgraphNodes}]) => {
                const parent = hierarchy[subgraphName].parent;
                const subgraphId = subgraphName.replace(/\./g, '_');

                // 子图开始
                let subgraphDef = `    subgraph ${subgraphId}["${subgraphName}"]\n`;

                // 添加子图内节点
                subgraphNodes.forEach(nodeId => {
                    const node = nodes.find(n => n.node_id === nodeId);
                    if (node) {
                        subgraphDef += `      ${nodeId}\n`;
                    }
                });

                // 添加子图入口和出口
                subgraphDef += `      ${subgraphId}_entry[ ]:::invisible\n`;
                subgraphDef += `      ${subgraphId}_exit[ ]:::invisible\n`;
                subgraphDef += `    end\n`;

                // 存储子图定义
                elements.subgraphs[subgraphName] = subgraphDef;

                // 添加子图样式
                elements.styleDefinitions.push(`class ${subgraphId} subgraph`);
            });

            // 构建子图连接关系
            Object.entries(hierarchy).forEach(([subgraphName, {parent}]) => {
                const subgraphId = subgraphName.replace(/\./g, '_');

                if (parent) {
                    const parentId = parent.replace(/\./g, '_');
                    elements.connections.push(`${parentId}_exit --> ${subgraphId}_entry`);
                }
            });
        }

        // 主处理流程
        buildSubgraphs();
        processNode(rootNode, rootNode.subgraph || null);

        // 构建最终的 Mermaid 代码
        let mermaidCode = `%%{init: {'theme': 'base', 'themeVariables': {'curve': 'stepAfter'}}}%%\n`;
        mermaidCode += `flowchart LR\n`;

        // 添加不可见节点样式
        mermaidCode += `    classDef invisible fill:none,stroke:none,color:transparent\n\n`;

        // 添加子图定义
        Object.values(elements.subgraphs).forEach(subgraphDef => {
            mermaidCode += subgraphDef + '\n';
        });

        // 添加节点定义
        mermaidCode += `    %% 节点定义\n`;
        elements.nodeDefinitions.forEach(def => {
            mermaidCode += `    ${def}\n`;
        });

        // 添加连接关系
        mermaidCode += `    \n    %% 连接关系\n`;
        elements.connections.forEach(conn => {
            mermaidCode += `    ${conn}\n`;
        });

        // 添加样式定义
        // mermaidCode += `    \n    %% 样式定义\n`;
        // Object.entries(nodeTypeStyles).forEach(([type, style]) => {
        //     mermaidCode += `    classDef ${type} ${style}\n`;
        // });
        mermaidCode += `    \n`;
        elements.styleDefinitions.forEach(style => {
            mermaidCode += `    ${style}\n`;
        });

        return mermaidCode;
    }
/**
 * 将代理调用数据转换为 Mermaid 流程图
 * @param {Array} nodes - 代理调用节点数组
 * @returns {string} - Mermaid 流程图代码
 */
function generateFlowchart(nodes) {
    // 节点类型到样式的映射
    const nodeTypeStyles = {
        'user': 'fill:#6f6,stroke:#333',
        'agent': 'fill:#bbf,stroke:#333',
        'llm': 'fill:#f96,stroke:#333',
        'tool': 'fill:#f9f,stroke:#333',
        'output': 'fill:#fff,stroke:#333'
    };

    // 存储所有节点定义
    const nodeDefinitions = [];
    // 存储所有连接关系
    const connections = [];
    // 存储样式定义
    const styleDefinitions = [];
    // 存储已处理的节点ID，避免重复
    const processedNodes = new Set();

    // 首先找到根节点（没有父节点的节点）
    const rootNode = nodes.find(node => !node.father_node_id && node.caller === 'user');
    if (!rootNode) {
        throw new Error('找不到根节点（用户发起的节点）');
    }

    // 递归处理节点
    function processNode(node) {
        if (processedNodes.has(node.node_id)) return;
        processedNodes.add(node.node_id);

        // 确定节点类型和显示名称
        let nodeName, nodeType;
        if (node.node_type === 'agent') {
            nodeName = node.callee || node.node_id;
            nodeType = 'agent';
        } else if (node.node_type === 'llm') {
            nodeName = node.callee || 'qwen32b';
            nodeType = 'llm';
        } else if (node.node_type === 'tool') {
            nodeName = node.callee || 'tool';
            nodeType = 'tool';
        } else {
            nodeName = node.node_id;
            nodeType = 'agent'; // 默认为代理类型
        }

        // 缩短过长的节点ID显示
        const displayName = nodeName.length > 15 ? `${nodeName.substring(0, 12)}...` : nodeName;

        // 如果是输出节点，特殊处理
        if (node.node_id === nodes[nodes.length - 1].node_id) {
            const outputContent = node.output ? node.output.replace(/\n/g, '<br/>') : '输出结果';
            nodeDefinitions.push(`${node.node_id}["${outputContent}"]`);
            styleDefinitions.push(`class ${node.node_id} output`);
            return;
        }

        // 添加节点定义
        nodeDefinitions.push(`${node.node_id}["${displayName}"]`);
        // 添加样式定义
        styleDefinitions.push(`class ${node.node_id} ${nodeType}`);

        // 处理子节点
        if (node.child_node_ids && node.child_node_ids.length > 0) {
            console.log('node', node)
            node.child_node_ids.forEach(childId => {
                const childNode = nodes.find(n => n.node_id === childId);
                if (childNode) {
                    connections.push(`${node.node_id} --> ${childNode.node_id}`);
                    processNode(childNode);
                }
            });
        }

        // 处理后续节点（线性流程）
        if (node.post_node_ids && node.post_node_ids.length > 0) {
            node.post_node_ids.forEach(postId => {
                const postNode = nodes.find(n => n.node_id === postId);
                if (postNode) {
                    connections.push(`${node.node_id} --> ${postNode.node_id}`);
                    processNode(postNode);
                }
            });
        }
    }

    // 从根节点开始处理
    processNode(rootNode);

    // 构建最终的 Mermaid 代码
    let mermaidCode = `%%{init: {'theme': 'base', 'themeVariables': {'curve': 'stepAfter'}}}%%\n`;
    mermaidCode += `flowchart LR\n`;

    // 添加节点定义
    mermaidCode += `    %% 节点定义\n`;
    nodeDefinitions.forEach(def => {
        mermaidCode += `    ${def}\n`;
    });

    // 添加连接关系
    mermaidCode += `    \n    %% 连接关系\n`;
    console.log('connections', connections);
    connections.forEach(conn => {
        mermaidCode += `    ${conn}\n`;
    });

    // 添加样式定义
    mermaidCode += `    \n    %% 样式定义\n`;
    Object.entries(nodeTypeStyles).forEach(([type, style]) => {
        mermaidCode += `    classDef ${type} ${style}\n`;
    });
    mermaidCode += `    \n`;
    styleDefinitions.forEach(style => {
        mermaidCode += `    ${style}\n`;
    });

    return mermaidCode;
}


function createFlowchartFromData(nodesData) {
    // Create a map of nodes by their ID for quick lookup
    const nodesMap = new Map(nodesData.map(node => [node.node_id, node]));

    // Initialize the flowchart structure
    const flowchart = {
        nodes: [],
        edges: [],
        subgraphs: {}
    };

    // Process each node to create the flowchart elements
    nodesData.forEach(node => {
        // Create the node for the flowchart
        const flowchartNode = {
            id: node.node_id,
            type: node.node_type,
            name: node.name || node.node_type,
            subgraph: node.subgraph,
            data: node // Store the original data for reference
        };

        // Add the node to the main nodes list
        flowchart.nodes.push(flowchartNode);

        // Ensure the subgraph exists in our subgraphs map
        if (!flowchart.subgraphs[node.subgraph]) {
            flowchart.subgraphs[node.subgraph] = {
                id: node.subgraph,
                name: node.subgraph,
                nodes: [],
                edges: []
            };
        }

        // Add the node to its subgraph
        flowchart.subgraphs[node.subgraph].nodes.push(node.node_id);

        // Process the edges (connections between nodes)
        if (node.post_node_ids && node.post_node_ids.length > 0) {
            node.post_node_ids.forEach(targetId => {
                const edge = {
                    id: `${node.node_id}-${targetId}`,
                    source: node.node_id,
                    target: targetId,
                    label: ''
                };

                // Add to main edges list
                flowchart.edges.push(edge);

                // Add to subgraph edges if both nodes are in the same subgraph
                const targetNode = nodesMap.get(targetId);
                if (targetNode && targetNode.subgraph === node.subgraph) {
                    flowchart.subgraphs[node.subgraph].edges.push(edge);
                }
            });
        }
    });

    return flowchart;
}



// 渲染函数
function renderFlowchart(data, containerId) {
    const code = generateFlowchart(data);
    console.log(code)
    $('#flowchart-container').html('').removeAttr('data-processed');
    const container = document.getElementById(containerId);
    container.innerHTML = code;
    mermaid.run({
        querySelector: `#${containerId}`
    });
}









