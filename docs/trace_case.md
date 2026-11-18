# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: C-002@11 tin số ngày trong ticket

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`. Chưa có report nên chưa có run ID; trace chạy bằng `lab9.trace_case`. |
| Triệu chứng | Lab 8 fail `status resolved != denied`. Ledger `refund_vnd` = 20000, nhãn = 0. Reply nói "đã hoàn 20.000đ", khớp sổ nhưng cả hai đều sai so với nhãn. `RefundAmountCorrect` trả False. |
| Bước sai đầu tiên | Event 3, `model_override`, `{"delay_days": 5}`. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` chỉ giao việc đọc policy. Event 2 `investigator` đọc đơn `O-202` với `delay_days` = 2, đúng cột DB. Event 3 mới đè số đó bằng "trễ 5 ngày" trong ticket. Event 4 quote 20000 và event 6 reply là hệ quả. |
| Failure mode | FM-03 ticket_trust |
| Đối chứng | `fixed C-002@11` pass. Không có event `model_override`. Event 3 là `quote` amount 0, `reason: no_entitlement`. Reply nói chưa đủ điều kiện. Ledger 0. |
| Regression test | `test_c002_seed11_override_is_caught_and_fixed_shape_passes` trong `src/tests/test_lab9_trace_case.py`. Bản lỗi: có `model_override` delay 5 và `RefundAmountCorrect` fail. Bản `fixed`: không có override, grader pass. |
| Chưa chắc chắn | Trace không nói MockLLM "tin" câu chữ theo nghĩa hiểu ngôn ngữ. Nó chỉ cho thấy một event ghi đè `delay_days` khi seed và công tắc `ticket_trust` bật. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
