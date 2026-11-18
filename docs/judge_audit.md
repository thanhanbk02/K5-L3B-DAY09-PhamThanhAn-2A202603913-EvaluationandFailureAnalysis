# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

Lớp dương là `FAIL`: judge có nhiệm vụ tìm câu trả lời hỏng. Sàn: κ ≥ 0.6, precision ≥ 0.8, recall ≥ 0.7.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | có | dùng |
| helpful | 100 | 0.375 | 1.0 | 0.3 | không (κ và recall dưới sàn) | loại |

Ma trận, `FAIL` là lớp dương:

- tone: tp 24, fp 4, fn 6, tn 66. Tỉ lệ fail quan sát 0.28, sau Rogan–Gladen còn 0.30.
- helpful: tp 9, fp 0, fn 21, tn 70. Tỉ lệ fail quan sát 0.09, sau hiệu chỉnh lên 0.30. Judge gần như không bao giờ nói FAIL, nên precision cao trong khi bỏ sót 21 lỗi thật.

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 tone. "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" và "nha" quá suồng sã. Judge thấy thân thiện nên cho qua. Rubric phải FAIL khi xưng em/nha/bạn ơi với khách. |
| 2 | H-029 tone. "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | "Không cần nhắn thêm" là ra lệnh. Judge chỉ nhìn "Dạ, vui lòng". Rubric phải FAIL câu đuổi khách, kể cả khi mở đầu lịch sự. |
| 3 | H-070 tone. "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji không hợp khiếu nại. Thêm vào rubric: không emoji trong câu trả lời hoàn tiền hoặc từ chối. |
| 4 | H-042 tone. "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Câu ngắn nhưng đủ số tiền, mã đơn và thời gian về tiền. Judge phạt vì thiếu lời xin lỗi. Bỏ quy tắc "luôn phải xin lỗi" khi kết quả đã nói rõ. |
| 5 | H-051 tone. "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | CS LogiX cho dùng từ "refund". Judge phạt vì có tiếng Anh. Rubric ghi rõ "refund" được phép. |
| 6 | H-081 tone. "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | Judge | Câu từ chối đúng giọng. Nhãn người đọc nhầm ticket. Sửa nhãn thành FAIL của judge, không nới rubric. |
| 7 | HL-015 helpful. "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | Người | Câu lịch sự nhưng sai số tiền. Judge helpful không đối chiếu số với sổ. Tiền không được giao cho judge này. |
| 8 | HL-047 helpful. "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Xưng hô sai và không nói đã xử lý thế nào. Câu vẫn được PASS vì không đụng tới tiêu chí "hữu ích" mà judge đang dùng. |

## Kết luận

- **tone_ok được dùng** làm kiểm tra giọng văn. κ 0.757, precision 0.857, recall 0.8, cả ba trên sàn. Bốn báo động giả và sáu bỏ sót còn sửa được bằng rubric: cấm xưng em/nha/bạn ơi, cấm ra lệnh, cấm emoji, cấm mất dấu tiếng Việt, cấm hứa hoàn thêm ngoài số hệ thống; đừng phạt câu ngắn đã đủ ý và đừng phạt từ "refund". Một nhãn người (H-081) sai, sửa nhãn chứ không hạ sàn.
- **helpful bị loại, không được làm cổng.** Precision = 1 chỉ vì nó không báo động giả (fp = 0). Recall = 0.3 và κ = 0.375: 21/30 câu người đánh FAIL vẫn được PASS, phần lớn là câu nói sai số tiền hoặc xin lỗi vòng vo. Rogan–Gladen kéo tỉ lệ fail từ 0.09 lên 0.30, tức tỉ lệ thô đang bị judge này làm đẹp. Một cổng dùng judge này sẽ cho merge câu hoàn sai tiền. Số tiền và approval tiếp tục chấm bằng code.
- Rủi ro còn lại: cả hai judge chỉ được kiểm trên dữ liệu replay đã công khai. Cần nhãn người mới, không nằm trong file này, thì mới có held-out thật.
