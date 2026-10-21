const form = document.getElementById('form-login');
const password = document.getElementById('password');
document.getElementById('toggle-password').addEventListener('click', (event) => {
  const visible = password.type === 'password';
  password.type = visible ? 'text' : 'password';
  event.currentTarget.textContent = visible ? 'Ocultar' : 'Mostrar';
  event.currentTarget.setAttribute('aria-pressed', String(visible));
});
