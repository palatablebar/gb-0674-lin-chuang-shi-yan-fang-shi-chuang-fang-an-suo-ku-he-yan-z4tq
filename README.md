# 临床试验访视窗与方案锁库核验

给临床试验数据管理员使用。按入组基准计算访视半开窗，方案修订按受试者生效时间选版；漏访不可用复检伪填。

七个业务模块：记录采信、方案版本、访视排窗、偏离复核、复检裁决、锁库检查、冻结归档。

```sh
docker compose up --build -d
docker compose exec -T app pytest -q
```

访问 http://localhost:18243 。启动直接载入现场脏批。切换干净样例和旧编码样例可对照核验。清批20个虚构受试者、40次应访视及5次复检，可锁库冻结。现场脏批包含窗末偏离、缺首次访视、错误复检引用及方案不符，必须处理后才能冻结。

各模块页面对应 `/<模块英文名>`，各模块执行入口为 `POST /api/<模块英文名>`，不传参即可独立演示。完整运行 `POST /api/runs` 支持 `dataset`（dirty/clean/legacy）、`csv_text` 与 `overrides` 参数。批次历史 `GET /api/runs`，详情 `GET /api/runs/{run_id}`。

同输入与规则版本生成相同批号，只保留一条批次。复核入口 `POST /api/runs/{run_id}/review` 提交当前 `revision`，陈旧提交409。归档包只有一个下载入口 `GET /api/export/{run_id}`，含证据和运行摘要。原始隔离在页面同屏显示。

SQLite使用命名卷，容器重启后保留历史。要重建演示可在Compose中改用新的卷名称，保留旧卷。

源码在 `app/`，样例在 `sample_data/`，测试在 `tests/`；定义见 `docs/DATA-DICTIONARY.md`，模块和边界测试对应关系见 `docs/DEPTH.md`。输入上限2MB，属于离线复核工具。

采信页支持上传或粘贴CSV。完整源字节与参数随批次持久化，跨页通过run_id读取同一结果。`POST /api/runs/{run_id}/rerun` 读取该批不可变输入快照重新计算，规则未变时批号不变。切换另一示例则创建或复用另一批次。
