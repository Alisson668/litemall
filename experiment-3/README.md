# 实验三：接口契约测试、智能 Fuzzing 与安全初探

## 范围

- 主要接口：`POST /wx/order/submit`
- 安全边界：JWT 身份来源、购物车 IDOR、订单详情 IDOR
- 语义载荷：类型混淆、极值、SQL 注入文本、畸形 JSON、无效 UTF-8、64 KiB 消息
- 契约元素：24 项，覆盖率 100%

## 一键复现

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\experiment3.ps1
```

脚本依次执行：

1. 运行 `WxOrderSubmitContractTest` 和 `WxOrderSubmitFuzzTest`
2. 打包 Java 8 JAR
3. 复制 JAR 并重启 litemall 容器
4. 等待 `http://localhost:8080/wx/home/index` 返回 200
5. 导出 Swagger 到 `experiment-3/openapi/wx-api-swagger.json`
6. 执行 16 个真实 HTTP Fuzzing/IDOR 用例并写入 `experiment-3/evidence`

## 结果

- 自动测试：32 / 32 通过
- 真实 HTTP Fuzzing/IDOR：16 / 16 通过
- 核心契约：24 / 24，100%
- 观测到的 HTTP 状态：200、405、406、415
- HTTP 5xx：0
- 越权与注入前置条件均未进入非法数据库查询

## 修复要点

- submit 只接受 `application/json`、只返回 `application/json`
- JSON 整数字段改为严格整数解析，拒绝字符串、布尔、数组、对象、小数和溢出值
- 缺失必填字段返回 `401`，字段值或类型错误返回 `402`
- 405、406、415 使用专用异常处理，不再落入通用后端错误
- 请求体中的 `userId` 不参与身份判断，身份始终来自 `X-Litemall-Token`
- 购物车与订单详情继续以认证用户 ID 作为归属查询条件
