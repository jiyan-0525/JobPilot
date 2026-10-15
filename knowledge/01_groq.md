# Groq 与 GPT-OSS

Groq 是一家提供超低延迟大模型推理服务的公司，它自研了 LPU（Language Processing Unit）芯片，
专门用于加速大语言模型的推理，速度通常比传统 GPU 方案快很多。

本项目通过 OpenAI 兼容接口访问 Groq，也就是把 base_url 指向
`https://api.groq.com/openai/v1`，然后像调用 OpenAI 一样调用它。

早期项目使用的是 `llama-3.1-8b-instant` 模型，但该模型已被 Groq 下架。
现在改用 `openai/gpt-oss-120b`，这是一个支持工具调用（tool calling）的模型。

使用 Groq 需要一个 API key，格式以 `gsk_` 开头。
如果 key 被提交到公开仓库，Groq 的密钥扫描可能会自动将其吊销。
