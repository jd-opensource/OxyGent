# 20行代码快速启动

## 安装环境
1. python环境（3.10及以上版本）
```bash
conda create -n oxy_env python==3.10
conda activate oxy_env
```

2. oxygent环境
```bash
pip install oxygent
```

3. Node.js环境（如果使用MCP工具）
[https://nodejs.org/zh-cn](https://nodejs.org/zh-cn) 下载安装即可

## Hello World
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/002.png)

新建 .env 文件设置环境变量：
```bash
DEFAULT_LLM_API_KEY    = "<填写大模型 api key>"
DEFAULT_LLM_BASE_URL   = "<填写大模型 base url>"
DEFAULT_LLM_MODEL_NAME = "<填写大模型 model name>"
```

启动
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/003.png)

## RAG
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/004.png)


![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/005.png)

## MoA
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/006.png)

<video controls="" muted="" height="50%" width="100%">
<source type="video/mp4" src="https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/007.mp4">
</video>

# 让智能体自主调用工具
## Local MCP 工具
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/008.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/009.png)

## SSE MCP 工具
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/010.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/011.png)

## FunctionHub 工具
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/012.png)

用任意工具注册方式（FunctionHub、LocalMCP、SSEMCP），启动后都是以下效果
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/013.png)

## 外部 MCP 工具
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/014.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/015.png)

## 自动召回topK个工具
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/016.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/017.png)

进入节点可视化页面
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/018.png)

# 积木式搭建多智能体
## 多智能体
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/019.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/020.png)

## 多层级智能体
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/021.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/022.png)

## 结合Workflow
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/023.png)

<video controls="" muted="" height="50%" width="100%">
<source type="video/mp4" src="https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/024.mp4">
</video>

## Reflexion机制
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/025.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/026.png)

Why?
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/027.png)

# 智能体快速部署
## 数据持久化
框架具备完善的数据存储机制，可用于后续的SFT训练或RL训练。
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/028.png)

## 限制任意节点的并发数量
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/029.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/030.png)

## 多环境配置部署
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/031.png)

## 分布式
![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/032.png)

![](https://storage.jd.com/ai-gateway-routing/prod_data/oxygent_sd_250801/033.png)

# 更多高阶用法

* 多模态
* 按权重过滤执行过程的Memory
* 检索更多工具
* 自定义大模型输出解析器
* 自定义SSE接口
* 结果后处理或格式化
* 智能体同时调用多个工具
* 从中间节点重启任务
* Plan-and-Solve范式
* ……

我们将会陆续整理发布，感谢您的支持与耐心！
