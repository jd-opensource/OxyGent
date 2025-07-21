// 级联选择器构造函数
function Cascader(config) {
    this.inputEl = document.querySelector(config.el);
    this.dropdownEl = document.querySelector(config.dropdown);
    this.options = config.options || [];
    this.onChange = config.onChange || function () {
    };
    this.selectedValues = [];
    this.selectedOptions = [];

    this.init();
}

Cascader.prototype.updateOptions = function(options) {
    this.options = options;
    this.selectedValues = [];
    this.selectedOptions = [];
};

Cascader.prototype.destroy = function() {
    if (this.$inputEl) {
        this.$inputEl.remove();
        this.$inputEl = null;
    }
};

// 初始化方法
Cascader.prototype.init = function () {
    this.renderInput();
    this.bindEvents();
};

// 渲染输入框
Cascader.prototype.renderInput = function () {
    var placeholder = this.inputEl.querySelector('.placeholder');
    // if (this.selectedOptions.length > 0) {
    //     var labels = this.selectedOptions.map(function (opt) {
    //         return opt.label;
    //     });
    //     placeholder.textContent = labels.join(' / ');
    //     placeholder.style.color = '#333';
    // } else {
    //     placeholder.textContent = '请选择';
    //     placeholder.style.color = '#999';
    // }
};

// 绑定事件
Cascader.prototype.bindEvents = function () {
    var self = this;

    // 输入框点击事件
    this.inputEl.addEventListener('click', function (e) {
        e.stopPropagation();
        self.toggleDropdown();
    });

    // 文档点击事件，用于关闭下拉菜单
    document.addEventListener('click', function () {
        self.hideDropdown();
    });
};

// 切换下拉菜单显示/隐藏
Cascader.prototype.toggleDropdown = function () {
    if (this.dropdownEl.classList.contains('show')) {
        this.hideDropdown();
    } else {
        this.showDropdown();
    }
};

// 显示下拉菜单
Cascader.prototype.showDropdown = function () {
    this.dropdownEl.classList.add('show');
    this.inputEl.querySelector('.arrow').classList.add('open');
    this.renderMenus();
};

// 隐藏下拉菜单
Cascader.prototype.hideDropdown = function () {
    this.dropdownEl.classList.remove('show');
    this.inputEl.querySelector('.arrow').classList.remove('open');
};

// 渲染级联菜单
Cascader.prototype.renderMenus = function () {
    var menusContainer = this.dropdownEl.querySelector('.cascader-menus');
    menusContainer.innerHTML = '';

    // 如果没有选择任何项，只显示第一级菜单
    if (this.selectedValues.length === 0) {
        var menu = this.createMenu(this.options, 0);
        menusContainer.appendChild(menu);
        return;
    }

    // 显示已选择的各级菜单
    var currentOptions = this.options;
    for (var i = 0; i < this.selectedValues.length; i++) {
        var menu = this.createMenu(currentOptions, i);
        menusContainer.appendChild(menu);

        // 高亮已选中的选项
        var selectedValue = this.selectedValues[i];
        var optionEls = menu.querySelectorAll('.cascader-option');
        for (var j = 0; j < optionEls.length; j++) {
            if (optionEls[j].dataset.value === selectedValue) {
                optionEls[j].classList.add('selected');
            }
        }

        // 查找下一级选项
        var selectedOption = null;
        for (var k = 0; k < currentOptions.length; k++) {
            if (currentOptions[k].value === selectedValue) {
                selectedOption = currentOptions[k];
                break;
            }
        }

        if (selectedOption && selectedOption.children) {
            currentOptions = selectedOption.children;
        } else {
            currentOptions = [];
        }
    }

    // 如果有子级，显示下一级菜单
    if (currentOptions && currentOptions.length > 0) {
        console.log(currentOptions);
        var nextMenu = this.createMenu(currentOptions, this.selectedValues.length);
        menusContainer.appendChild(nextMenu);
    }
};

// 创建单个菜单
Cascader.prototype.createMenu = function (options, level) {
    var menu = document.createElement('div');
    menu.className = 'cascader-menu';

    var self = this;

    options.forEach(function (option) {
        var optionEl = document.createElement('div');
        var icon = option.image ? `<img src="${option.image}" />` : '';


        optionEl.id = option.id;
        optionEl.className = 'cascader-option';

        optionEl.dataset.value = option.value;
        optionEl.dataset.level = level;

        optionEl.innerHTML = icon + option.label +
            (option.children ? '<img alt="#" src="./image/arrow-right.svg" class="arrow"></img>' : '');

        optionEl.addEventListener('click', function (e) {
            e.stopPropagation();
            self.handleOptionClick(option, level);
        });

        menu.appendChild(optionEl);
    });

    return menu;
};


// 处理选项点击
Cascader.prototype.handleOptionClick = function (option, level) {
    console.log(option);
    // 更新选中值
    this.selectedValues = this.selectedValues.slice(0, level);
    this.selectedOptions = this.selectedOptions.slice(0, level);

    this.selectedValues.push(option.value);
    this.selectedOptions.push({
        value: option.value,
        label: option.label
    });

    // 如果没有子级，则关闭下拉菜单
    if (!option.children || option.children.length === 0) {
        this.hideDropdown();
        this.renderInput();
        this.onChange(this.selectedValues, this.selectedOptions);
        this.selectedValues = [];
        return;
    }

    // 重新渲染菜单
    this.renderMenus();
};




