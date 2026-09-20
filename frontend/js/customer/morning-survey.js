/**
 * Student Daily Morning Survey Controller
 * Manages daily dining survey submission, duplicate prevention, and completion state.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const API_BASE = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

    const loadingEl = document.getElementById('survey-loading');
    const formViewEl = document.getElementById('survey-form-view');
    const completedViewEl = document.getElementById('survey-completed-view');
    const alertEl = document.getElementById('survey-alert');
    const alertTextEl = document.getElementById('survey-alert-text');
    const alertIconEl = document.getElementById('survey-alert-icon');
    const surveyForm = document.getElementById('morningSurveyForm');
    const submitBtn = document.getElementById('submit-survey-btn');
    const todayDateBadge = document.getElementById('today-date-badge');

    // Display human-readable today date
    const todayObj = new Date();
    const dateFormatted = todayObj.toLocaleDateString('en-IN', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    });
    if (todayDateBadge) {
        todayDateBadge.textContent = dateFormatted;
    }

    function showAlert(message, type = 'error') {
        if (!alertEl || !alertTextEl) return;
        alertEl.classList.remove('hidden', 'bg-rose-50', 'border-rose-200', 'text-rose-800', 'bg-emerald-50', 'border-emerald-200', 'text-emerald-800', 'bg-amber-50', 'border-amber-200', 'text-amber-800');

        if (type === 'success') {
            alertEl.classList.add('bg-emerald-50', 'border-emerald-200', 'text-emerald-800');
            if (alertIconEl) alertIconEl.className = 'fa-solid fa-circle-check text-base text-emerald-600';
        } else if (type === 'warning') {
            alertEl.classList.add('bg-amber-50', 'border-amber-200', 'text-amber-800');
            if (alertIconEl) alertIconEl.className = 'fa-solid fa-triangle-exclamation text-base text-amber-600';
        } else {
            alertEl.classList.add('bg-rose-50', 'border-rose-200', 'text-rose-800');
            if (alertIconEl) alertIconEl.className = 'fa-solid fa-circle-exclamation text-base text-rose-600';
        }

        alertTextEl.textContent = message;
        alertEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideAlert() {
        if (alertEl) alertEl.classList.add('hidden');
    }

    // 1. Authoritative Backend Session Verification
    let currentUser = null;
    try {
        const authRes = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
        if (!authRes.ok) {
            window.location.href = '../auth/login.html';
            return;
        }
        const authData = await authRes.json();
        if (!authData.authenticated || !authData.user || authData.user.role !== 'customer') {
            window.location.href = '../auth/login.html';
            return;
        }
        currentUser = authData.user;
    } catch (e) {
        console.error('Auth verification error:', e);
        window.location.href = '../auth/login.html';
        return;
    }

    let currentTodaySurvey = null;
    let isEditMode = false;
    const urlParams = new URLSearchParams(window.location.search);
    const requestedEdit = urlParams.get('edit') === '1' || urlParams.get('edit') === 'true';

    // 2. Render Completed Survey State
    function showCompletedSurvey(survey) {
        currentTodaySurvey = survey;
        isEditMode = false;
        if (loadingEl) loadingEl.classList.add('hidden');
        if (formViewEl) formViewEl.classList.add('hidden');
        if (completedViewEl) completedViewEl.classList.remove('hidden');

        const dateEl = document.getElementById('completed-survey-date');
        const plansEl = document.getElementById('summary-plans-to-eat');
        const mealPrefEl = document.getElementById('summary-meal-pref');
        const hungerEl = document.getElementById('summary-hunger');
        const dietEl = document.getElementById('summary-diet');
        const mealTypeEl = document.getElementById('summary-meal-type');

        if (dateEl) dateEl.textContent = `Recorded on ${survey.survey_date || dateFormatted}`;
        if (plansEl) plansEl.textContent = survey.plans_to_eat ? 'YES — PLANNING TO EAT' : 'NO — NOT TODAY';
        if (mealPrefEl) mealPrefEl.textContent = survey.meal_preference || 'General Campus Specials';
        if (hungerEl) hungerEl.textContent = (survey.hunger_level || 'Moderate').toUpperCase();
        if (dietEl) dietEl.textContent = (survey.dietary_preference || 'Any').toUpperCase();
        if (mealTypeEl) mealTypeEl.textContent = (survey.meal_type || 'Breakfast').replace('_', ' ').toUpperCase();

        const extraContainer = document.getElementById('summary-extra-container');
        let hasExtra = false;

        const moodLine = document.getElementById('summary-mood-line');
        const moodVal = document.getElementById('summary-mood');
        if (survey.mood_energy) {
            if (moodVal) moodVal.textContent = survey.mood_energy;
            if (moodLine) moodLine.classList.remove('hidden');
            hasExtra = true;
        }

        const restrLine = document.getElementById('summary-restrictions-line');
        const restrVal = document.getElementById('summary-restrictions');
        if (survey.food_restrictions) {
            if (restrVal) restrVal.textContent = survey.food_restrictions;
            if (restrLine) restrLine.classList.remove('hidden');
            hasExtra = true;
        }

        const notesLine = document.getElementById('summary-notes-line');
        const notesVal = document.getElementById('summary-notes');
        if (survey.notes) {
            if (notesVal) notesVal.textContent = survey.notes;
            if (notesLine) notesLine.classList.remove('hidden');
            hasExtra = true;
        }

        if (extraContainer && hasExtra) {
            extraContainer.classList.remove('hidden');
        }
    }

    // Enter Edit Mode for Existing Survey
    function enterEditMode(survey) {
        if (!survey) return;
        currentTodaySurvey = survey;
        isEditMode = true;

        if (loadingEl) loadingEl.classList.add('hidden');
        if (completedViewEl) completedViewEl.classList.add('hidden');
        if (formViewEl) formViewEl.classList.remove('hidden');

        // Populate form inputs
        const planRadios = document.querySelectorAll('input[name="plans_to_eat"]');
        planRadios.forEach(r => { r.checked = String(survey.plans_to_eat !== false) === r.value; });

        const mealPrefRadios = document.querySelectorAll('input[name="meal_preference"]');
        mealPrefRadios.forEach(r => {
            if (r.value === survey.meal_preference) r.checked = true;
        });

        const hungerRadios = document.querySelectorAll('input[name="hunger_level"]');
        hungerRadios.forEach(r => {
            if (r.value === survey.hunger_level) r.checked = true;
        });

        const dietSelect = document.getElementById('dietary_preference');
        if (dietSelect && survey.dietary_preference) {
            dietSelect.value = survey.dietary_preference;
        }

        const mealTypeSelect = document.getElementById('meal_type');
        if (mealTypeSelect && survey.meal_type) {
            mealTypeSelect.value = survey.meal_type;
        }

        const moodInput = document.getElementById('mood_energy');
        if (moodInput) moodInput.value = survey.mood_energy || '';

        const restrictionsInput = document.getElementById('food_restrictions');
        if (restrictionsInput) restrictionsInput.value = survey.food_restrictions || '';

        const notesInput = document.getElementById('notes');
        if (notesInput) notesInput.value = survey.notes || '';

        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk mr-1.5"></i> Update Preferences';
        }
    }

    const editBtn = document.getElementById('edit-survey-btn');
    if (editBtn) {
        editBtn.addEventListener('click', () => {
            if (currentTodaySurvey) {
                enterEditMode(currentTodaySurvey);
            }
        });
    }

    // 3. Check Today's Survey Status from Authoritative Backend
    async function checkTodaySurvey() {
        try {
            const res = await fetch(`${API_BASE}/customer/survey/today`, { credentials: 'include' });
            if (res.status === 401) {
                window.location.href = '../auth/login.html';
                return;
            }

            const data = await res.json();
            if (data.success && data.completed && data.survey) {
                currentTodaySurvey = data.survey;
                if (requestedEdit) {
                    enterEditMode(data.survey);
                } else {
                    showCompletedSurvey(data.survey);
                }
            } else {
                // Not yet completed: show form
                isEditMode = false;
                if (loadingEl) loadingEl.classList.add('hidden');
                if (completedViewEl) completedViewEl.classList.add('hidden');
                if (formViewEl) formViewEl.classList.remove('hidden');
            }
        } catch (e) {
            console.error('Error fetching today survey:', e);
            if (loadingEl) loadingEl.classList.add('hidden');
            showAlert('Could not connect to the survey service. Please check your connection.', 'error');
            if (formViewEl) formViewEl.classList.remove('hidden');
        }
    }

    await checkTodaySurvey();

    // Load vendor-published menus for today and group them by breakfast/lunch/dinner.
    async function loadTodayMenus() {
        const container = document.getElementById('today-menu-list');
        if (!container) return;
        try {
            const res = await fetch(`${API_BASE}/menu/today`, { credentials: 'include' });
            const data = await res.json();
            if (!data.success || !data.shops || data.shops.length === 0) {
                container.innerHTML = '<p class="text-xs text-slate-400">No vendors have published today\'s menu yet.</p>';
                return;
            }
            const periods = [['breakfast','Breakfast','fa-sun'],['lunch','Lunch','fa-bowl-food'],['dinner','Dinner','fa-moon']];
            container.innerHTML = data.shops.map(shop => {
                const sections = periods.map(p => {
                    const items = shop[p[0]] || [];
                    const body = items.length ? items.map(item => `<div class="flex justify-between gap-2 text-[11px] py-1 border-b border-slate-50 last:border-0"><span class="text-slate-600 truncate">${item.name}</span><span class="font-bold text-slate-800 shrink-0">₹${Number(item.price).toFixed(2)}</span></div>`).join('') : '<span class="text-[10px] text-slate-400">Not published</span>';
                    return `<div class="bg-white rounded-xl border border-slate-100 p-2.5"><div class="flex items-center gap-1.5 mb-1.5 text-xs font-black text-slate-700"><i class="fa-solid ${p[2]} text-teal-500"></i>${p[1]}</div>${body}</div>`;
                }).join('');
                return `<div class="border border-slate-100 rounded-2xl p-3 bg-slate-50/60"><div class="flex items-center justify-between mb-2"><span class="text-xs font-black text-slate-800">${shop.shop_name}</span><span class="text-[10px] text-slate-400">Today's published menu</span></div><div class="grid grid-cols-1 md:grid-cols-3 gap-2">${sections}</div></div>`;
            }).join('');
        } catch (e) {
            console.debug('Today menu load error:', e);
            container.innerHTML = '<p class="text-xs text-rose-500">Could not load today\'s vendor menus.</p>';
        }
    }

    await loadTodayMenus();

    // 4. Handle Form Submission
    if (surveyForm) {
        surveyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlert();

            const mealPrefRadio = document.querySelector('input[name="meal_preference"]:checked');
            const hungerRadio = document.querySelector('input[name="hunger_level"]:checked');
            const dietSelect = document.getElementById('dietary_preference');
            const mealTypeSelect = document.getElementById('meal_type');
            const moodInput = document.getElementById('mood_energy');
            const restrictionsInput = document.getElementById('food_restrictions');
            const notesInput = document.getElementById('notes');

            if (!mealPrefRadio) {
                showAlert('Please select your preferred taste or food category for today.', 'error');
                return;
            }

            const planRadio = document.querySelector('input[name="plans_to_eat"]:checked');
            const payload = {
                plans_to_eat: planRadio ? planRadio.value === 'true' : true,
                meal_preference: mealPrefRadio.value,
                hunger_level: hungerRadio ? hungerRadio.value : 'moderate',
                dietary_preference: dietSelect ? dietSelect.value : 'any',
                meal_type: mealTypeSelect ? mealTypeSelect.value : 'breakfast',
                mood_energy: moodInput ? moodInput.value.trim() : '',
                food_restrictions: restrictionsInput ? restrictionsInput.value.trim() : '',
                notes: notesInput ? notesInput.value.trim() : ''
            };

            const origBtnHtml = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> ${isEditMode ? 'Updating Preferences...' : 'Saving Preferences...'}`;
            }

            const method = isEditMode ? 'PUT' : 'POST';
            try {
                const res = await fetch(`${API_BASE}/customer/survey`, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if ((res.status === 200 || res.status === 201) && data.success && data.survey) {
                    showAlert(isEditMode ? '✓ Morning preferences updated successfully!' : '✓ Morning survey saved successfully! Updating recommendations...', 'success');
                    setTimeout(() => {
                        showCompletedSurvey(data.survey);
                    }, 600);
                } else if (res.status === 409) {
                    showAlert('You have already completed today’s survey. Loading your recorded responses...', 'warning');
                    await checkTodaySurvey();
                } else {
                    showAlert(data.message || 'Unable to submit survey. Please review your entries.', 'error');
                }
            } catch (err) {
                console.error('Survey submission error:', err);
                showAlert('Network error while saving survey. Please try again.', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = origBtnHtml;
                }
            }
        });
    }
});
