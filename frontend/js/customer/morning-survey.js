document.addEventListener('DOMContentLoaded', loadFoodSurvey);

const API_BASE = window.FOOD_COURT_API_BASE ||
    (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

let foodSurveyData = null;
let foodSurveyTimer = null;
let lastOpenMeal = null;

async function loadFoodSurvey() {
    try {
        const auth = await fetch(API_BASE + '/auth/me', { credentials: 'include' });
        const authData = await auth.json();
        if (!auth.ok || !authData.authenticated || authData.user.role !== 'customer') {
            location.href = '../auth/login.html';
            return;
        }

        const res = await fetch(API_BASE + '/customer/morning-poll/today', { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || 'Unable to load Food Survey.');

        foodSurveyData = data;
        document.getElementById('poll-loading').classList.add('hidden');
        const surveys = data.surveys || [];
        const list = document.getElementById('poll-list');

        if (!surveys.length) {
            document.getElementById('poll-empty').classList.remove('hidden');
            return;
        }

        list.innerHTML = surveys.map(renderSurvey).join('');
        attachFoodSurveyHandlers();
        startFoodSurveyClock();
    } catch (e) {
        document.getElementById('poll-loading').classList.add('hidden');
        showPollMessage(e.message || 'Unable to load Food Survey.', false);
    }
}

function mealLabel(period) {
    return period.charAt(0).toUpperCase() + period.slice(1);
}

function formatTime(value) {
    if (!value) return '—';
    const parts = String(value).split(':').map(Number);
    const d = new Date();
    d.setHours(parts[0], parts[1], 0, 0);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function mealIcon(period) {
    return period === 'breakfast' ? '🍳' : period === 'lunch' ? '🍛' : '🌙';
}

function renderSurvey(survey) {
    const options = survey.options || [];
    const periods = ['breakfast', 'lunch', 'dinner'];
    const votedByPeriod = survey.voted_menu_item_ids_by_period || {};

    const sections = periods.map(function(period) {
        const rows = options.filter(function(option) {
            return String(option.meal_period || '').toLowerCase() === period;
        });
        const win = (survey.meal_windows || {})[period] || {};
        const status = win.status || 'closed';
        const isOpen = status === 'open';
        const votedIds = votedByPeriod[period] || [];
        const isVoted = votedIds.length > 0;

        const stateText = isVoted
            ? 'Survey submitted'
            : isOpen
                ? formatTime(win.start_time) + ' – ' + formatTime(win.end_time) + ' · OPEN NOW'
                : status === 'upcoming'
                    ? formatTime(win.start_time) + ' – ' + formatTime(win.end_time) + ' · UPCOMING'
                    : formatTime(win.start_time) + ' – ' + formatTime(win.end_time) + ' · CLOSED';

        const cardClass = isOpen
            ? 'border-teal-200 bg-teal-50/40'
            : isVoted
                ? 'border-emerald-200 bg-emerald-50/40'
                : 'border-slate-200 bg-slate-50';

        let rowsHtml = '';
        if (rows.length) {
            rowsHtml = '<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">' +
                rows.map(function(option) {
                    const selected = votedIds.map(String).includes(String(option.id));
                    return '<label class="food-vote-option block rounded-2xl border-2 ' +
                        (selected ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 bg-white') +
                        ' ' + (isOpen && !isVoted ? 'cursor-pointer hover:border-teal-400' : 'cursor-default') + ' p-4 transition-all">' +
                        '<input type="checkbox" name="food-choice-' + survey.survey_id + '-' + period +
                        '" value="' + option.id + '" class="food-vote-checkbox w-5 h-5 accent-teal-600 flex-none" data-period="' + period + '"' +
                        (selected ? ' checked' : '') + ((!isOpen || isVoted) ? ' disabled' : '') + '>' +
                        '<div class="flex items-center justify-between gap-3 mt-2"><div class="min-w-0">' +
                        '<p class="font-black text-slate-900">' + escapeHtml(option.item_name) + '</p>' +
                        '<p class="text-xs text-slate-400 mt-1">₹' + Number(option.price || 0).toFixed(2) + '</p></div>' +
                        '<span class="food-vote-check w-7 h-7 rounded-full border-2 ' +
                        (selected ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-slate-300 bg-white text-transparent') +
                        ' flex items-center justify-center flex-none"><i class="fa-solid fa-check text-xs"></i></span></div></label>';
                }).join('') + '</div>';
        } else {
            rowsHtml = '<div class="rounded-2xl bg-white/70 border border-dashed border-slate-200 p-5 text-center text-xs text-slate-400">No ' +
                period + ' dishes published by this vendor.</div>';
        }

        const submit = isOpen && !isVoted && rows.length
            ? '<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-4 pt-4 border-t border-slate-200">' +
              '<p class="text-[11px] text-slate-500">Select one or more dishes and submit once for ' + mealLabel(period) + '.</p>' +
              '<button type="button" data-submit-food-vote="' + survey.survey_id + '" data-meal-period="' + period +
              '" class="px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:bg-slate-300 text-white text-xs font-black">Submit ' +
              mealLabel(period) + ' Survey</button></div>' : '';

        return '<div class="rounded-3xl border ' + cardClass + ' p-4 sm:p-5 mb-4">' +
            '<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4"><div>' +
            '<h3 class="font-black text-slate-900">' + mealIcon(period) + ' ' + mealLabel(period) + '</h3>' +
            '<p class="text-[11px] text-slate-500 mt-1">' + escapeHtml(stateText) + '</p></div>' +
            '<span class="px-3 py-1.5 rounded-full text-[10px] font-black uppercase ' +
            (isVoted ? 'bg-emerald-100 text-emerald-700' : isOpen ? 'bg-teal-100 text-teal-700' : status === 'upcoming' ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-500') +
            '">' + (isVoted ? 'Submitted' : status === 'open' ? 'Open Now' : status === 'upcoming' ? 'Upcoming' : 'Closed') + '</span></div>' +
            rowsHtml + submit + '</div>';
    }).join('');

    return '<section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-5 sm:p-6">' +
        '<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5"><div>' +
        '<p class="text-[10px] font-black uppercase tracking-widest text-teal-600">Food Survey · ' + escapeHtml(survey.date || '') + '</p>' +
        '<h2 class="text-xl font-black text-slate-900 mt-1">' + escapeHtml(survey.shop_name || 'Food Court') + '</h2>' +
        '<p class="text-xs text-slate-400 mt-1">Breakfast, lunch and dinner demand survey. One submission is allowed for each meal period.</p></div>' +
        '<span class="px-3 py-1.5 rounded-full text-[10px] font-black bg-blue-50 text-blue-700">IST · Asia/Kolkata</span></div>' +
        sections + '</section>';
}

function attachFoodSurveyHandlers() {
    document.querySelectorAll('.food-vote-checkbox').forEach(function(input) {
        input.addEventListener('change', function() {
            const card = this.closest('.food-vote-option');
            if (!card) return;
            card.classList.toggle('border-teal-500', this.checked);
            card.classList.toggle('bg-teal-50', this.checked);
            card.classList.toggle('border-slate-200', !this.checked);
            card.classList.toggle('bg-white', !this.checked);
            const check = card.querySelector('.food-vote-check');
            if (check) {
                check.classList.toggle('border-teal-600', this.checked);
                check.classList.toggle('bg-teal-600', this.checked);
                check.classList.toggle('text-white', this.checked);
                check.classList.toggle('border-slate-300', !this.checked);
                check.classList.toggle('text-transparent', !this.checked);
            }
        });
    });

    document.querySelectorAll('[data-submit-food-vote]').forEach(function(button) {
        button.addEventListener('click', function() {
            submitFoodVote(Number(this.dataset.submitFoodVote), this.dataset.mealPeriod);
        });
    });
}

async function submitFoodVote(surveyId, mealPeriod) {
    const selected = Array.from(document.querySelectorAll(
        'input[name="food-choice-' + surveyId + '-' + mealPeriod + '"]:checked'
    ));

    if (!selected.length) {
        showPollMessage('Please select at least one ' + mealLabel(mealPeriod).toLowerCase() + ' dish.', false);
        return;
    }

    const button = document.querySelector('[data-submit-food-vote="' + surveyId + '"][data-meal-period="' + mealPeriod + '"]');

    try {
        if (button) {
            button.disabled = true;
            button.textContent = 'Submitting...';
        }

        const res = await fetch(API_BASE + '/customer/morning-poll/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                survey_id: surveyId,
                meal_period: mealPeriod,
                menu_item_ids: selected.map(function(input) { return Number(input.value); })
            })
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || 'Unable to record Food Survey.');

        showPollMessage(data.message || mealLabel(mealPeriod) + ' Food Survey submitted successfully.', true);
        await loadFoodSurvey();
    } catch (e) {
        showPollMessage(e.message || 'Unable to record Food Survey.', false);
        if (button) {
            button.disabled = false;
            button.textContent = 'Submit ' + mealLabel(mealPeriod) + ' Survey';
        }
    }
}

function startFoodSurveyClock() {
    if (foodSurveyTimer) clearInterval(foodSurveyTimer);
    foodSurveyTimer = setInterval(function() {
        const now = new Date();
        const parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Kolkata',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
        }).formatToParts(now);
        const current = {};
        parts.forEach(function(p) { current[p.type] = Number(p.value); });
        const seconds = current.hour * 3600 + current.minute * 60 + current.second;

        const periods = ['breakfast', 'lunch', 'dinner'];
        const windows = foodSurveyData && foodSurveyData.surveys && foodSurveyData.surveys[0]
            ? foodSurveyData.surveys[0].meal_windows || {} : {};

        periods.forEach(function(period) {
            const w = windows[period];
            if (!w) return;
            const a = String(w.start_time).split(':').map(Number);
            const b = String(w.end_time).split(':').map(Number);
            const start = a[0] * 3600 + a[1] * 60;
            const end = b[0] * 3600 + b[1] * 60;
            if (seconds >= start && seconds < end) {
                if (lastOpenMeal !== period) {
                    lastOpenMeal = period;
                    loadFoodSurvey();
                    return;
                }
                document.querySelectorAll('[data-period-status="' + period + '"]').forEach(function(el) {
                    if (el.textContent.toLowerCase() !== 'submitted') el.textContent = 'Open Now';
                });
            }
        });
    }, 1000);
}

function showPollMessage(message, success) {
    const element = document.getElementById('poll-message');
    element.textContent = message;
    element.className = 'mb-5 p-4 rounded-2xl text-sm font-bold ' +
        (success ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' : 'bg-rose-50 border border-rose-200 text-rose-700');
    element.classList.remove('hidden');
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, function(character) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character];
    });
}
