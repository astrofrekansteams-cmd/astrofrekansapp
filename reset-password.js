const status = document.getElementById('status');
const button = document.getElementById('open-app');
const hash = new URLSearchParams(location.hash.slice(1));
// Query links from older emails remain usable. New links use the fragment so
// the reset token never reaches the static host in an HTTP request.
const query = new URLSearchParams(location.search);
const token = hash.get('token') || query.get('token');
history.replaceState(null, '', location.pathname);

if (token) {
  status.textContent = 'Şifrenizi değiştirmek için uygulamayı açın.';
  button.hidden = false;
  button.addEventListener('click', () => {
    location.href = `astrofrekans://app/reset-password?token=${encodeURIComponent(token)}`;
  });
} else {
  status.textContent = 'Bağlantıda sıfırlama kodu bulunamadı. Uygulamadan yeni bir bağlantı isteyin.';
}
