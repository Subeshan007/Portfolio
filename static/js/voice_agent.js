(function() {
  const transcriptEl = document.getElementById('transcript');
  const startBtn = document.getElementById('start-voice');
  const stopBtn = document.getElementById('stop-voice');
  const fallback = document.getElementById('fallback-form');

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supportsVoice = !!(SpeechRecognition && window.speechSynthesis);

  if (!supportsVoice) {
    if (fallback) fallback.hidden = false;
    if (startBtn) startBtn.disabled = true;
    appendAgent('Your browser does not support voice; please use the form below.');
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.continuous = false;

  let dialogState = 'idle';
  let formData = {
    patient_name: '',
    age: '',
    contact: '',
    reason: '',
    preferred_date: '',
    preferred_time: '',
    doctor_id: ''
  };

  function appendAgent(text) {
    const div = document.createElement('div');
    div.className = 'msg agent';
    div.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }
  function appendUser(text) {
    const div = document.createElement('div');
    div.className = 'msg user';
    div.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function speak(text, onend) {
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.pitch = 1.0;
    utter.onend = onend || null;
    window.speechSynthesis.speak(utter);
  }

  function ask(question, nextState) {
    dialogState = nextState;
    appendAgent(question);
    speak(question, () => recognition.start());
  }

  function startDialog() {
    transcriptEl.innerHTML = '';
    formData = { patient_name: '', age: '', contact: '', reason: '', preferred_date: '', preferred_time: '', doctor_id: '' };
    ask('Hello! I will help you book a healthcare appointment. What is your full name?', 'await_name');
  }

  function parseDate(str) {
    // Expect YYYY-MM-DD for reliability
    const m = String(str).trim().match(/(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})/);
    if (!m) return null;
    const [_, y, mo, d] = m;
    return `${y}-${mo.padStart(2,'0')}-${d.padStart(2,'0')}`;
  }
  function parseTime(str) {
    // Expect HH:MM 24h
    const m = String(str).trim().match(/(\d{1,2}):(\d{2})/);
    if (!m) return null;
    let [_, hh, mm] = m;
    hh = String(hh).padStart(2,'0');
    return `${hh}:${mm}`;
  }

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript.trim();
    appendUser(text);

    if (dialogState === 'await_name') {
      formData.patient_name = text;
      ask('Thanks. How old are you?', 'await_age');
      return;
    }
    if (dialogState === 'await_age') {
      const age = parseInt(text.replace(/[^0-9]/g, ''), 10);
      formData.age = isNaN(age) ? '' : age;
      ask('What is the best phone number or email to contact you?', 'await_contact');
      return;
    }
    if (dialogState === 'await_contact') {
      formData.contact = text;
      ask('Briefly describe the reason for your appointment.', 'await_reason');
      return;
    }
    if (dialogState === 'await_reason') {
      formData.reason = text;
      ask('What date works best? Please say the date as year dash month dash day. For example, 2025-08-15.', 'await_date');
      return;
    }
    if (dialogState === 'await_date') {
      const parsed = parseDate(text);
      if (!parsed) { ask('I did not catch the date. Please say it as 2025-08-15.', 'await_date'); return; }
      formData.preferred_date = parsed;
      ask('At what time? Please say the time in 24 hour format, like 14:30.', 'await_time');
      return;
    }
    if (dialogState === 'await_time') {
      const parsed = parseTime(text);
      if (!parsed) { ask('I did not catch the time. Please say it like 14:30.', 'await_time'); return; }
      formData.preferred_time = parsed;

      const doctors = Array.isArray(window.CAREVOICE_DOCTORS) ? window.CAREVOICE_DOCTORS : [];
      if (doctors.length === 0) {
        ask('Do you have a preferred doctor? You can say no preference.', 'await_doctor');
      } else {
        const names = doctors.map(d => d.username + (d.specialty ? `, ${d.specialty}` : '')).slice(0,5).join('; ');
        ask(`Do you have a preferred doctor? For example: ${names}. You can also say no preference.`, 'await_doctor');
      }
      return;
    }
    if (dialogState === 'await_doctor') {
      const doctors = Array.isArray(window.CAREVOICE_DOCTORS) ? window.CAREVOICE_DOCTORS : [];
      const lower = text.toLowerCase();
      if (lower.includes('no') && lower.includes('preference')) {
        formData.doctor_id = '';
      } else if (doctors.length > 0) {
        const match = doctors.find(d => lower.includes(String(d.username).toLowerCase()));
        formData.doctor_id = match ? String(match._id) : '';
      }
      const summary = `Please confirm: Name ${formData.patient_name}. Age ${formData.age || 'unspecified'}. Contact ${formData.contact}. Reason ${formData.reason}. Date ${formData.preferred_date}. Time ${formData.preferred_time}. ${formData.doctor_id ? 'Preferred doctor selected.' : 'No doctor preference.'} Should I submit?`;
      ask(summary, 'await_confirm');
      return;
    }
    if (dialogState === 'await_confirm') {
      const yes = /\b(yes|yeah|yep|correct|submit)\b/i.test(text);
      if (!yes) { ask('Okay, let us try again. What is your full name?', 'await_name'); return; }
      submitAppointment();
      return;
    }
  };

  recognition.onerror = (e) => {
    appendAgent('Speech error: ' + e.error);
  };

  function submitAppointment() {
    appendAgent('Submitting your appointment...');
    fetch('/api/appointments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    }).then(r => r.json())
      .then(data => {
        if (data.ok) {
          appendAgent('Your appointment request was created successfully. Thank you!');
          speak('Your appointment request was created successfully.');
          const textForm = document.getElementById('text-booking');
          if (textForm) textForm.reset();
        } else {
          appendAgent('There was an error: ' + data.error);
          speak('There was an error.');
        }
      })
      .catch(err => {
        appendAgent('Network error: ' + err.message);
        speak('Network error.');
      });
  }

  startBtn.addEventListener('click', () => {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    startDialog();
  });
  stopBtn.addEventListener('click', () => {
    try { recognition.stop(); } catch {}
    startBtn.disabled = false;
    stopBtn.disabled = true;
    appendAgent('Stopped. You can press Start to begin again.');
  });
})();