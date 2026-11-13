# Demo scenario — "Shift handover and line fault at an electronics assembly plant" (~30 min)

**Setting.** An electronics assembly plant in an industrial park in Bắc Ninh. Production line 3 assembles control boards.
The interpreter runs offline on one device placed on the line-side table: Arduino VENTUNO Q (QCS8275, NPU), the QCS8550 meeting tablet, or a Samsung Galaxy S25 Ultra (SM8750) running the CabinTranslation app. The two
speakers stand on either side of it, about 40–60 cm from the microphone. Light background noise from fans and conveyors.

**Roles**

| Role | Language | Who |
|---|---|---|
| Lan — line leader (tổ trưởng chuyền 3) | Vietnamese | team member A |
| Mr. James Carter — customer quality auditor | English | team member B |
| Mr. Kim Min-jun — equipment engineer from the Korean machine supplier | Korean | team member C (or B) |
| Ms. Wang Li — QA representative of the Chinese component supplier | Chinese | team member D (or B) |

**How to operate.** Pick the partner language at the top of the UI. The Vietnamese speaker holds **🎤 Giữ để nói**,
and the partner holds **🎤 Hold to talk**. Each turn is one sentence or two short ones. The status line shows the
ASR / MT / TTS time. Each scene ends with a recap read back by the device.

| # | Time | Pair | Scene |
|---|---|---|---|
| 0 | 00:00–02:00 | — | Show device, **disable network** (airplane mode on the tablet / S25 Ultra; Wi-Fi off and cable out on VENTUNO Q), start the app, ready state |
| 1 | 02:00–08:00 | VI ↔ EN | Safety briefing and line walk with the auditor |
| 2 | 08:00–14:00 | VI ↔ KO | Reflow-oven alarm: troubleshooting with the Korean engineer |
| 3 | 14:00–20:00 | VI ↔ ZH | Defective connectors: incoming inspection with the Chinese supplier |
| 4 | 20:00–25:00 | VI ↔ EN | Audit findings, numbers, dates and corrective actions |
| 5 | 25:00–29:00 | VI ↔ KO / ZH | Shift handover, confirmation of next steps |
| 6 | 29:00–30:00 | — | Show logs / timings; still offline |

## Scene 1 — Safety briefing (VI ↔ EN)

| Speaker | Utterance |
|---|---|
| Lan (vi) | Chào anh James, tôi là Lan, tổ trưởng chuyền số ba. |
| James (en) | Nice to meet you, Lan. Can you walk me through the line today? |
| Lan (vi) | Trước khi vào xưởng, anh vui lòng đeo giày chống tĩnh điện và đội mũ. |
| James (en) | Do I also need a wrist strap at the workstation? |
| Lan (vi) | Có, khi chạm vào bo mạch thì phải đeo vòng tĩnh điện. |
| James (en) | How many operators work on this line per shift? |
| Lan (vi) | Mỗi ca có hai mươi tư công nhân, chia làm ba trạm. |
| James (en) | What is your daily output target? |
| Lan (vi) | Mục tiêu là một nghìn hai trăm bo mạch mỗi ngày. |
| James (en) | Where do you keep the rejected boards? |
| Lan (vi) | Hàng lỗi để trong thùng màu đỏ ở cuối chuyền, có dán nhãn. |
| James (en) | Okay, please show me the inspection station first. |

## Scene 2 — Reflow-oven alarm (VI ↔ KO)

| Speaker | Utterance |
|---|---|
| Lan (vi) | Anh Kim ơi, lò hàn số hai báo lỗi nhiệt độ từ sáng nay. |
| Kim (ko) | 언제부터 알람이 울렸어요? |
| Lan (vi) | Khoảng bảy giờ ba mươi, ngay sau khi đổi ca. |
| Kim (ko) | 화면에 에러 코드가 뭐라고 나와요? |
| Lan (vi) | Mã lỗi là E bốn mươi hai, vùng nhiệt số năm. |
| Kim (ko) | 먼저 전원을 끄고 십 분 동안 식혀 주세요. |
| Lan (vi) | Chúng tôi đã tắt máy rồi, bây giờ có cần thay cảm biến không? |
| Kim (ko) | 네, 센서를 확인해야 해요. 예비 부품이 있어요? |
| Lan (vi) | Trong kho còn hai cảm biến dự phòng. |
| Kim (ko) | 좋아요. 교체한 후에 온도 프로파일을 다시 측정할게요. |
| Lan (vi) | Mất khoảng bao lâu thì chuyền chạy lại được? |
| Kim (ko) | 한 시간 정도 걸릴 거예요. |

## Scene 3 — Defective connectors (VI ↔ ZH)

| Speaker | Utterance |
|---|---|
| Lan (vi) | Chào chị Vương, lô đầu nối hôm qua có nhiều chân bị cong. |
| Wang (zh) | 有多少个不良品？ |
| Lan (vi) | Chúng tôi kiểm tra năm trăm cái, có ba mươi hai cái bị lỗi. |
| Wang (zh) | 请给我看一下照片和批号。 |
| Lan (vi) | Số lô là hai không hai sáu một một không năm. |
| Wang (zh) | 这批货是上个星期从深圳工厂发出的。 |
| Lan (vi) | Chị có thể đổi hàng trong tuần này không? |
| Wang (zh) | 可以，我们明天会安排新的货。 |
| Lan (vi) | Từ lô sau, xin chị đóng gói bằng khay chống va đập. |
| Wang (zh) | 好的，我会通知包装部门。 |

## Scene 4 — Audit findings (VI ↔ EN)

| Speaker | Utterance |
|---|---|
| James (en) | I found two issues during the walk. |
| Lan (vi) | Anh cứ nói, tôi sẽ ghi lại. |
| James (en) | First, the fire extinguisher at station two expired last month. |
| Lan (vi) | Tôi sẽ thay bình chữa cháy trước chiều nay. |
| James (en) | Second, the torque values are not recorded on the night shift. |
| Lan (vi) | Ca đêm sẽ ghi lực siết vào biểu mẫu sau mỗi hai giờ. |
| James (en) | When can you send me the corrective action report? |
| Lan (vi) | Tôi sẽ gửi báo cáo khắc phục trước ngày hai mươi tháng mười một. |
| James (en) | Great. Overall the line is clean and well organized. |
| Lan (vi) | Cảm ơn anh, chúng tôi sẽ tiếp tục cải tiến. |

## Scene 5 — Shift handover (VI ↔ KO, VI ↔ ZH)

| Speaker | Utterance |
|---|---|
| Lan (vi) | Anh Kim, lò hàn đã chạy ổn định chưa? |
| Kim (ko) | 네, 센서를 교체했고 온도가 정상이에요. |
| Lan (vi) | Ca tối cần lưu ý điều gì không? |
| Kim (ko) | 두 시간마다 온도 기록을 확인해 주세요. |
| Lan (vi) | Chị Vương, hàng đổi sẽ đến lúc mấy giờ ngày mai? |
| Wang (zh) | 明天上午十点左右到。 |
| Lan (vi) | Cảm ơn mọi người, hôm nay chúng ta kết thúc ở đây. |

## What the judges should see

- The network is disabled on camera before the first exchange (Scene 0). The device keeps working through all scenes.
- Each turn shows the recognized source sentence, the translation, the spoken output, and the per-stage time.
- Numbers, dates, error codes and lot numbers are carried over correctly (scenes 2–4).
- If an utterance is misrecognized, the speaker presses again and repeats it. The 🔊 button replays the last translation.
