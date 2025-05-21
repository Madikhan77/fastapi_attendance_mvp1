const btn = document.getElementById('mark-btn');
const status = document.getElementById('status');
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');

btn.addEventListener('click', async () => {
  status.textContent = '';
  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  video.srcObject = stream;
  video.classList.remove('hidden');
  btn.textContent = 'Делаем снимок...';

  setTimeout(async () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const blob = await new Promise(resolve => canvas.toBlob(resolve));
    const form = new FormData(); form.append('file', blob);
    const lessonId = location.pathname.split('/').pop();
    const res = await fetch(`/api/attendance/${lessonId}`, { method: 'POST', body: form });
    const data = await res.json();
    status.textContent = res.ok ? '✅ Отмечено!' : '❌ ' + data.detail;
    stream.getTracks().forEach(t => t.stop());
    video.classList.add('hidden');
    btn.textContent = 'Отметить присутствие';
  }, 1000);
});