import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockCreateClient = vi.fn();

vi.mock('@supabase/supabase-js', () => {
    return {
        createClient: (...args) => {
            mockCreateClient(...args);
            return { mockSupabaseClient: true };
        }
    }
});

describe('supabaseClient', () => {
    beforeEach(() => {
        vi.stubEnv('VITE_SUPABASE_URL', 'https://mock-url.supabase.co');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'mock-key');
    });

    afterEach(() => {
        vi.unstubAllEnvs();
        vi.clearAllMocks();
        vi.resetModules();
    });

    it('initializes with env variables', async () => {
        // dynamic import so that it picks up the stubbed env variables
        await import('../supabaseClient.js');
        expect(mockCreateClient).toHaveBeenCalledWith('https://mock-url.supabase.co', 'mock-key');
    });
});
