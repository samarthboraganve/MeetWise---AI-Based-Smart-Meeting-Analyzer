(function () {
    const LOGIN_PATH = '/static/login.html';
    const REGISTER_PATH = '/static/register.html';
    const nativeFetch = window.fetch.bind(window);

    const state = {
        initialized: false,
        initializing: null,
        enabled: false,
        client: null,
        user: null,
    };

    function notify(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
            return;
        }
        console.log(`[auth:${type}] ${message}`);
    }

    function getUserDisplayName(user) {
        if (!user) return 'Guest';

        const metadata = user.user_metadata || {};
        return metadata.full_name
            || metadata.name
            || metadata.user_name
            || user.email
            || 'Guest';
    }

    function getCurrentUrl() {
        return `${window.location.pathname}${window.location.search}${window.location.hash}`;
    }

    function normalizeNextUrl(candidate, fallback = '/static/dashboard.html') {
        if (!candidate) {
            return fallback;
        }

        try {
            const url = new URL(candidate, window.location.origin);

            if (url.origin !== window.location.origin) {
                return fallback;
            }

            return `${url.pathname}${url.search}${url.hash}`;
        } catch (_error) {
            return fallback;
        }
    }

    function getNextUrl(fallback) {
        const params = new URLSearchParams(window.location.search);
        return normalizeNextUrl(params.get('next'), fallback || '/static/dashboard.html');
    }

    function buildAuthUrl(path, options = {}) {
        const url = new URL(path, window.location.origin);

        if (options.nextUrl) {
            url.searchParams.set('next', normalizeNextUrl(options.nextUrl));
        }

        if (options.reason) {
            url.searchParams.set('reason', options.reason);
        }

        if (options.email) {
            url.searchParams.set('email', options.email);
        }

        if (options.registered) {
            url.searchParams.set('registered', '1');
        }

        return url.toString();
    }

    function redirectTo(path, options = {}) {
        window.location.href = buildAuthUrl(path, options);
    }

    function updateAuthUi() {
        const signedIn = Boolean(state.user);
        const displayName = getUserDisplayName(state.user);

        document.querySelectorAll('[data-auth-display]').forEach((node) => {
            node.textContent = displayName;
        });

        document.querySelectorAll('[data-auth-status]').forEach((node) => {
            node.textContent = signedIn
                ? `Signed in as ${displayName}`
                : 'Register or log in to unlock teams, meetings, and summaries.';
        });

        document.querySelectorAll('[data-auth-toggle]').forEach((button) => {
            button.textContent = signedIn ? 'Log Out' : 'Log In';
            button.dataset.authMode = signedIn ? 'logout' : 'login';
        });

        document.dispatchEvent(new CustomEvent('meetwise-auth-changed', {
            detail: {
                user: state.user,
                signedIn,
            },
        }));
    }

    async function fetchAuthConfig() {
        const response = await nativeFetch('/api/config/auth');
        if (!response.ok) {
            throw new Error('Unable to load auth configuration');
        }
        return response.json();
    }

    async function init() {
        if (state.initialized) {
            return state;
        }

        if (state.initializing) {
            return state.initializing;
        }

        state.initializing = (async () => {
            try {
                const config = await fetchAuthConfig();
                state.enabled = Boolean(config.enabled && config.url && config.anon_key);

                if (!state.enabled) {
                    console.warn('[auth] Supabase auth is not configured.');
                    return state;
                }

                if (!window.supabase || typeof window.supabase.createClient !== 'function') {
                    console.warn('[auth] Supabase client library was not loaded.');
                    return state;
                }

                state.client = window.supabase.createClient(config.url, config.anon_key, {
                    auth: {
                        persistSession: true,
                        autoRefreshToken: true,
                        detectSessionInUrl: true,
                    },
                });

                const { data, error } = await state.client.auth.getSession();
                if (error) {
                    throw error;
                }

                state.user = data.session ? data.session.user : null;

                state.client.auth.onAuthStateChange((_event, session) => {
                    state.user = session ? session.user : null;
                    updateAuthUi();
                });
            } catch (error) {
                console.error('[auth] Failed to initialize auth:', error);
            } finally {
                state.initialized = true;
                state.initializing = null;
                updateAuthUi();
            }

            return state;
        })();

        return state.initializing;
    }

    async function ensureClient() {
        await init();

        if (!state.enabled || !state.client) {
            notify('Supabase auth is not configured yet. Add SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY first.', 'error');
            return null;
        }

        return state.client;
    }

    async function getAccessToken() {
        const client = await ensureClient();
        if (!client) {
            return null;
        }

        const { data, error } = await client.auth.getSession();
        if (error) {
            console.error('[auth] Failed to get session:', error);
            return null;
        }

        state.user = data.session ? data.session.user : null;
        return data.session ? data.session.access_token : null;
    }

    async function authFetch(input, init = {}) {
        let requestUrl;

        try {
            const source = typeof input === 'string' ? input : input.url;
            requestUrl = new URL(source, window.location.origin);
        } catch (_error) {
            return nativeFetch(input, init);
        }

        const isProtectedApiRequest = requestUrl.origin === window.location.origin
            && requestUrl.pathname.startsWith('/api/')
            && requestUrl.pathname !== '/api/config/auth';

        if (!isProtectedApiRequest) {
            return nativeFetch(input, init);
        }

        const headers = new Headers(
            init.headers || (typeof input !== 'string' && input.headers) || undefined
        );
        const accessToken = await getAccessToken();

        if (accessToken) {
            headers.set('Authorization', `Bearer ${accessToken}`);
        }

        const response = await nativeFetch(input, {
            ...init,
            headers,
        });

        if (response.status === 401 && window.location.pathname !== LOGIN_PATH && window.location.pathname !== REGISTER_PATH) {
            redirectTo(LOGIN_PATH, { nextUrl: getCurrentUrl() });
            throw new Error('Authentication required');
        }

        return response;
    }

    async function signOut() {
        const client = await ensureClient();
        if (!client) return;

        try {
            const { error } = await client.auth.signOut();
            if (error) {
                throw error;
            }

            state.user = null;
            updateAuthUi();
            notify('Signed out.', 'success');

            if (window.location.pathname === LOGIN_PATH || window.location.pathname === REGISTER_PATH) {
                return;
            }

            window.location.href = '/static/index.html';
        } catch (error) {
            console.error('[auth] Sign-out failed:', error);
            notify(error.message || 'Sign-out failed.', 'error');
        }
    }

    async function requireAuth(options = {}) {
        const {
            reason,
            onAuthenticated,
            nextUrl = getCurrentUrl(),
            route = 'register',
        } = options;

        await init();

        if (state.user) {
            if (typeof onAuthenticated === 'function') {
                return onAuthenticated(state.user);
            }
            return state.user;
        }

        if (!state.enabled) {
            notify('Supabase auth is not configured yet. Add SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY first.', 'error');
            return null;
        }

        redirectTo(route === 'login' ? LOGIN_PATH : REGISTER_PATH, { nextUrl, reason });
        return null;
    }

    function getUser() {
        return state.user;
    }

    function getClient() {
        return state.client;
    }

    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-auth-toggle]');
        if (!button) return;

        if (button.dataset.authMode === 'logout') {
            signOut();
            return;
        }

        redirectTo(LOGIN_PATH, { nextUrl: getCurrentUrl() });
    });

    window.MeetWiseAuth = {
        init,
        ensureClient,
        getAccessToken,
        fetch: authFetch,
        requireAuth,
        signOut,
        getUser,
        getClient,
        getNextUrl,
        normalizeNextUrl,
        getUserDisplayName,
        buildAuthUrl,
        redirectTo,
        paths: {
            login: LOGIN_PATH,
            register: REGISTER_PATH,
        },
    };

    window.fetch = authFetch;
    init();
})();
