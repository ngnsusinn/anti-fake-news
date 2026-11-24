export function createResultView(panel, detail) {
  return {
    clear() {
      panel.hidden = true;
      detail.textContent = '';
    },
    render(data, mode) {
      const mock = mode === 'mock' || data.model_id === 'dev-mock-not-a-model';
      detail.textContent = [
        mock ? 'Giả lập dev/test. Không dùng làm kết quả nghiên cứu.' : 'Dự đoán của mô hình. Hãy đối chiếu nguồn.',
        'Nhãn: ' + (data.label === 'fake' ? 'Nghi tin giả (fake)' : 'Nghi tin thật (real)'),
        'Điểm fake_score: ' + data.fake_score + ' (thang 0–1, chưa hiệu chuẩn thành xác suất).',
        'Mô hình: ' + data.model_id + ', phiên bản ' + data.model_version,
        'Thời gian xử lý: ' + data.processing_time_ms + ' ms.',
        data.text_truncated ? 'Mô hình đã cắt bớt văn bản.' : 'Văn bản không bị cắt.',
      ].join(' ');
      panel.hidden = false;
      return mock;
    },
  };
}
