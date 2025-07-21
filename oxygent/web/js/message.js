// 实现一个简单的message
// Message SDK
(function($) {
    // 定义 Message 类
    function Message() {
        this.$container = null;
    }

    // 初始化消息容器
    Message.prototype.init = function() {
         this.$container = $('<div class="message-sdk" style="position: fixed; top: 20px; left: 50%; transform: translateX(-50%); width: 200px; padding: 10px; background: #333; color: white; text-align: center; border-radius: 4px; z-index: 9999;"></div>');
        
        $('body').append(this.$container);
        return this;
    };

    // 显示消息
    Message.prototype.show = function(content) {
        if (!this.$container) {
            this.init();
        }
        this.$container.html(content).fadeIn(200);
        
        // 100ms 后自动消失
        const self = this;
        setTimeout(function() {
            self.$container.fadeOut(200, function() {
                // 动画完成后销毁
                self.destroy();
            });
        }, 500);
    };

    // 销毁消息容器
    Message.prototype.destroy = function() {
        if (this.$container) {
            this.$container.remove();
            this.$container = null;
        }
    };

    // 对外暴露的 API
    window.MessageSDK = {
        show: function(content) {
            const msg = new Message();
            msg.show(content);
        }
    };
})(jQuery);

