
function renderFlowchart(agentNodes, containerId) {
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

        return { displayName, nodeType, callee: node.callee };
    }

    function createNodeElement(node) {
        const { displayName, nodeType, callee } = getNodeDisplayInfo(node);

        let preImg;
        if (nodeType === 'tool') {
            preImg = `<img style="padding: 5px;" src="${typeMap.tool}" alt="">`;
        } else if (nodeType === 'llm') {
            preImg = `<img style="padding: 5px;" src="${typeMap.llm}" alt="">`;
        } else {
            const idx = agent_id_dict[callee] % 16;
            const cur = agentImgMap[idx];

            preImg = `<img style="background-color: ${cur?.bgColor}; border-radius: 4px;" src="${cur?.imgUrl}" alt="">`;
        }

        if (node.child_node_ids && node.child_node_ids.length > 0) {
            const container = document.createElement('div');
            container.className = 'view1-container';
            container.id = node.node_id;

            const label = document.createElement('div');
            label.className = 'view1-label';
            label.innerHTML = `
                ${preImg}
                <span>${displayName}</span>
            `;
            label.onclick = e => {
                e.stopPropagation();
                container.classList.toggle('view1-collapsed');
            };
            container.appendChild(label);

            const content = document.createElement('div');
            content.className = 'view1-content';
            const childFlow = buildFlow(node.child_node_ids, node.node_id);
            childFlow.forEach(el => content.appendChild(el));
            container.appendChild(content);
            return container;
        } else {
            const element = document.createElement('div');
            element.className = 'view1-node';
            element.innerHTML = `
                ${preImg}
                <span class="hhh">${displayName}</span>
            `;
            element.id = node.node_id;
            return element;
        }
    }


    function createArrow() {
        const arrow = document.createElement('div');
        arrow.className = 'arrow';
        return arrow;
    }

    function buildFlow(nodeIds, parentId) {
        const elements = [];
        const processed = new Set();
        let currentIds = nodeIds.filter(id => {
            const node = nodesMap.get(id);
            return !node.pre_node_ids || node.pre_node_ids.length === 0 || node.pre_node_ids.every(preId => !nodeIds.includes(preId))
        });

        while (currentIds.length > 0) {
            const nextIds = new Set();

            // Group by parallel_id
            const parallelGroups = new Map();
            const singleNodes = [];

            currentIds.forEach(id => {
                const node = nodesMap.get(id);
                if (node.parallel_id) {
                    if (!parallelGroups.has(node.parallel_id)) {
                        parallelGroups.set(node.parallel_id, []);
                    }
                    parallelGroups.get(node.parallel_id).push(id);
                } else {
                    singleNodes.push(id);
                }
            });

            const groupElements = [];

            // Process parallel groups
            parallelGroups.forEach(ids => {
                const parallelContainer = document.createElement('div');
                parallelContainer.className = 'view1-parallel-container';
                ids.forEach(id => {
                    const node = nodesMap.get(id);
                    const branch = document.createElement('div');
                    branch.className = 'view1-parallel-branch';

                    const flow = buildFlow(node.child_node_ids, node.node_id);
                    const nodeElement = createNodeElement(node);
                    // Since buildFlow is recursive, we need to handle child flows within parallel branches
                    if (nodeElement.classList.contains('view1-container')) {
                        branch.appendChild(nodeElement);
                    } else {
                        const simpleFlow = document.createElement('div');
                        simpleFlow.className = 'view1-flowchart';
                        simpleFlow.appendChild(nodeElement);
                        branch.appendChild(simpleFlow);
                    }

                    parallelContainer.appendChild(branch);
                    processed.add(id);
                    if (node.post_node_ids) {
                        node.post_node_ids.forEach(nid => nextIds.add(nid));
                    }
                });
                groupElements.push(parallelContainer);
            });

            // Process single nodes
            singleNodes.forEach(id => {
                const node = nodesMap.get(id);
                groupElements.push(createNodeElement(node));
                processed.add(id);
                if (node.post_node_ids) {
                    node.post_node_ids.forEach(nid => nextIds.add(nid));
                }
            });

            if (elements.length > 0) {
                elements.push(createArrow());
            }

            if (groupElements.length > 1) {
                const parallelJoin = document.createElement('div');
                parallelJoin.className = 'view1-parallel-join';
                const container = document.createElement('div');
                container.className = 'view1-parallel-container';
                groupElements.forEach(el => container.appendChild(el));
                parallelJoin.appendChild(container);
                elements.push(parallelJoin);
            } else {
                elements.push(...groupElements);
            }

            currentIds = Array.from(nextIds).filter(id => !processed.has(id));
        }

        return elements;
    }

    const rootNode = agentNodes.find(node => !node.father_node_id);
    const nodesMap = new Map(agentNodes.map(node => [node.node_id, node]));

    if (rootNode) {
        // We will render the children of the root, as the root itself is just a logical container
        const flowchartElements = buildFlow(rootNode.child_node_ids, rootNode.node_id);
        const container = document.getElementById(containerId);
        $('#flowchart-container').html('').removeAttr('data-processed');
        flowchartElements.forEach(el => container.appendChild(el));
    }
}