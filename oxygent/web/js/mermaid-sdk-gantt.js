function formatTimeWithMilliseconds(timeString) {
    // 拆分日期和时间部分
    const [datePart, timePart] = timeString.split(' ');

    // 拆分时间部分
    const [hms, fractions] = timePart.split('.');

    // 提取前3位毫秒（如果不足3位则补0）
    const milliseconds = fractions ? fractions.substring(0, 3).padEnd(3, '0') : '000';

    // 组合成新格式
    return `${datePart} ${hms}.${milliseconds}`;
}

function unionName(data) {
    return [...new Set(data)]
}


function generateGrant(taskList) {
    let ganttCode = `gantt \n`;
    ganttCode += `dateFormat  YYYY-MM-DD HH:mm:ss.SSS \n`;
    // 添加节(Section)
    // ganttCode += `    section 项目阶段\n`;
    // 添加任务
    taskList.forEach(task => {
        if (task.sectionName) {
            ganttCode += `section ${task.sectionName}\n`;
        }
        if (task.data) {
            task.data.forEach(_task => {
                ganttCode += `    ${_task.name} :${_task.id}, ${_task.start}, ${_task.end}\n`;
                ganttCode += `    click ${_task.id} call renderGanttClick(${_task.id})\n`;
                ganttCode += '\n';
            })
        }

    });
    return ganttCode;
}


function renderGantt(nodesDatas, containerId) {

    const callerArray = nodesDatas.map(({caller}) => caller);
    const unionNamecallerArray = unionName(callerArray);

    const transformData = nodesDatas.map(_data => {
        return {
            ..._data,
            id: _data.node_id,
            next: _data.child_node_ids.filter(i => i),
            name: _data.callee,
            start: formatTimeWithMilliseconds(_data.create_time),
            end: formatTimeWithMilliseconds(_data.update_time),
        }
    })

    const transformDataSection = unionNamecallerArray.map((_caller) => {
        return {
            sectionName: _caller,
            data: transformData.filter(i => i.caller === _caller),
        }
    })

    const code = generateGrant(transformDataSection);
    $('#flowchart-container-gantt').html('').removeAttr('data-processed');
    const container = document.getElementById(containerId);
    container.innerHTML = code;
    mermaid.run({
        querySelector: `#${containerId}`
    });
}








