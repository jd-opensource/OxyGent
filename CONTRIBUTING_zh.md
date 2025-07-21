<!-- Copyright 2025 JD.com

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this project except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License. -->

[English](./CONTRIBUTING.md) | [中文](./CONTRIBUTING_zh.md)

# OxyGent 贡献指南

OxyGent致力于为每一位用户和开发者提供开放的智能体系统体验，因此无论您是资深智能体系统开发者还是专注于MAS应用的用户，我们都欢迎您参与我们的项目。
您可以通过以下方法为项目作出贡献：

+ 撰写/翻译/修改文档
+ 提出或回答问题
+ 提供使用或测试样例
+ 提供建议或其他评论
+ 参与[issues](https://github.com/jd-opensource/OxyGent/issues) 或[discussions](https://github.com/jd-opensource/OxyGent/discussions)
+ 提交Pull request
+ 分享相关研究或应用场景
+ 其他任何对OxyGent的帮助

如果您希望参与OxyGent的开发，请参考以下提示：

## 1. 选择参与贡献的issue
+ 您可以选择带有`PR welcome`标签的issue，包括:
    + 可复现的bug
    + 计划实现的功能

## 2. 配置开发环境
+ 在开发之前，可以参考我们的 **[文档](http://oxygent.jd.com/docs/)**
+ 关于环境配置，参见 **[Readme file](/README.md)**

## 3. 项目构建和运行
+ 您可以运行如下样例：
```bash
    python demo.py
```
```bash
    python -m examples.agents.single_demo
```

## 4. 测试
+ 在提交pr之前，可以使用`pytest`运行项目本地测试：
```bash
    pip install pytest pytest-asyncio
```
+ 格式化代码
```bash
    ruff format .
    docformatter -r -i --wrap-summaries 88 --wrap-descriptions 88 oxygent/
```
+ 运行单元测试:
```bash
    pytest oxygent/test/unittest
```
+ 运行样例综合测试（可选）:
```bash
    pytest oxygent/test/integration
```
在pr提交之后，我们会对代码进行格式化及进一步测试。
我们的测试目前还很不完善，因此欢迎开发者为测试作出贡献！