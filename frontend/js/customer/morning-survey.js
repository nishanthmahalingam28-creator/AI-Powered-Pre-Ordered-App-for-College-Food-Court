document.addEventListener('DOMContentLoaded', loadMorningPoll);

const API_BASE = window.FOOD_COURT_API_BASE ||
    (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

async function loadMorningPoll() {
    try {
        const auth = await fetch(API_BASE + '/auth/me', { credentials: 'include' });
        const authData = await auth.json();

        if (!auth.ok || !authData.authenticated || authData.user.role !== 'customer') {
            location.href = '../auth/login.html';
            return;
        }

        const res = await fetch(API_BASE + '/customer/morning-poll/today', {
            credentials: 'include'
        });
        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Unable to load morning survey.');
        }

        document.getElementById('poll-loading').classList.add('hidden');

        const list = document.getElementById('poll-list');
        const surveys = data.surveys || [];

        if (!surveys.length) {
            document.getElementById('poll-empty').classList.remove('hidden');
            return;
        }

        list.innerHTML = surveys.map(renderSurvey).join('');
        attachFoodChoiceHandlers();
    } catch (e) {
        document.getElementById('poll-loading').classList.add('hidden');
        showPollMessage(e.message || 'Unable to load morning survey.', false);
    }
}

function renderSurvey(survey) {
    const options = survey.options || [];
    const grouped = { breakfast: [], lunch: [], dinner: [] };

    options.forEach(option => {
        const period = String(option.meal_period || 'lunch').toLowerCase();
        if (!grouped[period]) grouped[period] = [];
        grouped[period].push(option);
    });

    const sections = Object.entries(grouped)
        .filter(([, rows]) => rows.length)
        .map(([period, rows]) => `
            <div class="mb-5">
                <p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">${period}</p>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    ${rows.map(option => {
                        const selected = String(survey.voted_menu_item_id) === String(option.id);
                        return `
                            <label class="food-vote-option block cursor-pointer rounded-2xl border-2 ${selected ? 'border-teal-500 bg-teal-50 ring-2 ring-teal-100' : 'border-slate-200 bg-white'} hover:border-teal-400 p-4 transition-all">
                                <input
                                    type="radio"
                                    name="food-choice-${survey.survey_id}"
                                    value="${option.id}"
                                    class="food-vote-radio w-5 h-5 accent-teal-600 flex-none cursor-pointer"
                                    ${selected ? 'checked' : ''}
                                    ${survey.voted ? 'disabled' : ''}
                                >
                                <div class="flex items-center justify-between gap-3">
                                    <div class="min-w-0">
                                        <p class="font-black text-slate-900">${escapeHtml(option.item_name)}</p>
                                        <p class="text-xs text-slate-400 mt-1">₹${Number(option.price || 0).toFixed(2)}</p>
                                    </div>
                                    <span class="food-vote-check w-7 h-7 rounded-full border-2 ${selected ? 'border-teal-600 bg-teal-600 text-white' : 'border-slate-300 bg-white text-transparent'} flex items-center justify-center flex-none">
                                        <i class="fa-solid fa-check text-xs"></i>
                                    </span>
                                </div>
                            </label>
                        `;
                    }).join('')}
                </div>
            </div>
        `).join('');

    return `
        <section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-5 sm:p-6">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
                <div>
                    <p class="text-[10px] font-black uppercase tracking-widest text-teal-600">Today's Food Vote</p>
                    <h2 class="text-xl font-black text-slate-900 mt-1">${escapeHtml(survey.shop_name || 'Food Court')}</h2>
                    <p class="text-xs text-slate-400 mt-1">Click one food item, then press Submit Food Vote.</p>
                </div>
                <span class="px-3 py-1.5 rounded-full text-[10px] font-black ${survey.voted ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}">
                    ${survey.voted ? '✓ Vote Recorded' : 'Choose One Food'}
                </span>
            </div>

            ${sections || '<p class="text-sm text-slate-400 text-center py-6">No food choices published for this shop yet.</p>'}

            <div class="flex justify-end mt-2">
                <button
                    type="button"
                    data-submit-food-vote="${survey.survey_id}"
                    class="px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white text-xs font-black transition-all ${survey.voted ? 'hidden' : ''}"
                >Submit Food Vote</button>
            </div>
        </section>
    `;
}

function attachFoodChoiceHandlers() {
    document.querySelectorAll('.food-vote-radio').forEach(radio => {
        radio.addEventListener('change', function () {
            const name = this.name;
            document.querySelectorAll('input[name="' + name + '"]').forEach(input => {
                const card = input.closest('.food-vote-option');
                if (!card) return;
                card.classList.toggle('border-teal-500', input.checked);
                card.classList.toggle('bg-teal-50', input.checked);
                card.classList.toggle('border-slate-200', !input.checked);
                card.classList.toggle('bg-white', !input.checked);
            });
        });
    });

    document.querySelectorAll('[data-submit-food-vote]').forEach(button => {
        button.addEventListener('click', function () {
            submitFoodVote(Number(this.dataset.submitFoodVote));
        });
    });
}
async function submitFoodVote(surveyId) {
    const selected = document.querySelector(`input[name="food-choice-${surveyId}"]:checked`);

    if (!selected) {
        showPollMessage('Please click a food item before voting.', false);
        return;
    }

    try {
        const button = document.querySelector(`[data-submit-food-vote="${surveyId}"]`);
        if (button) {
            button.disabled = true;
            button.textContent = 'Submitting...';
        }

        const res = await fetch(API_BASE + '/customer/morning-poll/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                survey_id: Number(surveyId),
                menu_item_id: Number(selected.value)
            })
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Unable to record vote.');
        }

        showPollMessage('Your food vote has been recorded successfully.', true);
        await loadMorningPoll();
    } catch (e) {
        showPollMessage(e.message || 'Unable to record vote.', false);

        const button = document.querySelector(`[data-submit-food-vote="${surveyId}"]`);
        if (button) {
            button.disabled = false;
            button.textContent = 'Submit Food Vote';
        }
    }
}

function showPollMessage(message, success) {
    const element = document.getElementById('poll-message');
    element.textContent = message;
    element.className =
        'mb-5 p-4 rounded-2xl text-sm font-bold ' +
        (success
            ? 'bg-emerald-50 border border-emerald-200 text-emerald-700'
            : 'bg-rose-50 border border-rose-200 text-rose-700');
    element.classList.remove('hidden');
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[character]));
}