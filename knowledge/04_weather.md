# 天气数据与 Open-Meteo

本项目最初的天气功能使用 OpenWeatherMap，需要申请 WEATHER_API_KEY。
后来改成了 Open-Meteo，因为它完全免费且不需要任何 API key。

Open-Meteo 的用法分两步：
第一步是地理编码，把城市名转成经纬度，接口是
`https://geocoding-api.open-meteo.com/v1/search`。
第二步是查询天气，接口是 `https://api.open-meteo.com/v1/forecast`，
可以指定 current 参数来获取当前温度、相对湿度和天气代码。

天气代码（weather_code）是 WMO 标准编码，例如 0 表示晴空、3 表示阴天、
61 表示小雨、95 表示雷暴。代码到文字的映射需要自己维护一张表。
