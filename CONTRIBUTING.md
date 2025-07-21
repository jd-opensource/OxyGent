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

# Contribute to OxyGent

Our project welcomes contributions from developers and organizations from all over the world. Our project is dedicated to creating a multi-agent development platform for all users, so whether you are an expert in your field or a regular user of the project, we welcome you to participate in shaping the future of this project. You can get involved in the project in the following ways:

+ Write / translate / fix our documentation
+ Raise questions / Answer questions
+ Provide demos, examples or test cases
+ Give suggestions or other comments
+ Paticipate in [issues](https://github.com/jd-opensource/OxyGent/issues) or [discussions](https://github.com/jd-opensource/OxyGent/discussions)
+ Pull requests
+ Sharing related research / application
+ Any other ways to improve OxyGent

For developers who want to contribute to our code, here is the guidance:

## 1. Choose an issue to contribute
+ Issues with label `PR welcome`, which means:
    + A reproducible bug
    + A function in plan

## 2. Install environment for development
+ We strongly suggest you to read our **[Document](http://oxygent.jd.com/docs/)** before developing
+ For setting environment, please check our  **[Readme file](/README.md)**

## 3. Build our project
+ You could run our demo to check whether the requirements are successfully installed:
```bash
    python demo.py
```
```bash
    python -m examples.agents.single_demo
```

## 4. Test
We provide some tests to check your code before pull request.
+ Before testing, you should install `pytest`:
```bash
    pip install pytest pytest-asyncio
```
+ Format code:
```bash
    ruff format .
    docformatter -r -i --wrap-summaries 88 --wrap-descriptions 88 oxygent/
```
+ Unit test:
```bash
    pytest oxygent/test/unittest
```
+ Integration test (Optional):
```bash
    pytest oxygent/test/integration
```
After the PR is submitted, we will format and test the code.
Our tests are still far from perfect, so you are welcomed to add tests to our project!