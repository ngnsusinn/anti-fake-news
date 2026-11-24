document.getElementById('load-content').addEventListener('click', () => {
  const article = document.createElement('article');
  const text = document.createElement('p');
  text.textContent = 'Bản tin mẫu xuất hiện sau khi trang nạp dữ liệu.';
  article.append(text);
  document.getElementById('content').replaceChildren(article);
});
