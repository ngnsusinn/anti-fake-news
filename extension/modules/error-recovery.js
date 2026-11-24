const messages = {
  config: 'Dùng địa chỉ http://127.0.0.1 và thời gian chờ từ 1.000 đến 120.000 mili giây.',
  network: 'Không kết nối được Backend. Kiểm tra địa chỉ, dịch vụ cục bộ và cấu hình quyền truy cập.',
  timeout: 'Tiện ích đã hết thời gian chờ. Backend có thể vẫn đang xử lý. Chọn Thử lại để gửi yêu cầu mới.',
  'invalid-response': 'Phản hồi Backend không hợp lệ. Kiểm tra phiên bản API rồi thử lại.',
  aborted: 'Đã dừng chờ phản hồi. Bạn có thể gửi lại yêu cầu.',
};
const httpMessages = {
  400: 'Backend từ chối đầu vào. Hãy rà lại nội dung và chọn lại ảnh JPEG/PNG nếu cần.',
  401: 'Token demo thiếu hoặc không đúng. Hãy sửa token trong phần Kết nối Backend.',
  403: 'Backend từ chối quyền truy cập. Hãy kiểm tra token và origin của tiện ích.',
  413: 'Yêu cầu vượt dung lượng. Hãy giảm dung lượng ảnh hoặc rút ngắn văn bản.',
  503: 'Backend chưa sẵn sàng. Hãy kiểm tra cấu hình hoặc chờ mô hình nạp xong.',
};

export function describeApiError(error) {
  if (error.kind === 'http') return httpMessages[error.status] ?? 'Backend trả lỗi. Hãy kiểm tra dịch vụ rồi thử lại.';
  return messages[error.kind] ?? 'Yêu cầu không thành công. Hãy thử lại.';
}

export function bindErrorRecovery(status, button) {
  let retry;
  button.addEventListener('click', () => retry?.());
  return {
    get hasRetry() { return typeof retry === 'function'; },
    show(error, action) {
      status.textContent = describeApiError(error);
      retry = action;
      button.hidden = false;
    },
    clear() {
      retry = undefined;
      button.hidden = true;
    },
  };
}
