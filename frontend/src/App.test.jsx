import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';
import { supabase } from './lib/supabaseClient';

// Mock all internal components since we're just testing the App routing
vi.mock('./components/Navbar', () => ({ default: () => <div data-testid="navbar" /> }));
vi.mock('./components/NoiseOverlay', () => ({ default: () => <div data-testid="noise-overlay" /> }));
vi.mock('./components/Hero', () => ({ default: () => <div data-testid="hero" /> }));
vi.mock('./components/Features', () => ({ default: () => <div data-testid="features" /> }));
vi.mock('./components/Philosophy', () => ({ default: () => <div data-testid="philosophy" /> }));
vi.mock('./components/Protocol', () => ({ default: () => <div data-testid="protocol" /> }));
vi.mock('./components/CTA', () => ({ default: () => <div data-testid="cta" /> }));
vi.mock('./components/Footer', () => ({ default: () => <div data-testid="footer" /> }));
vi.mock('./components/Auth', () => ({ default: () => <div data-testid="auth" /> }));
vi.mock('./components/UpdatePassword', () => ({ default: () => <div data-testid="update-password" /> }));

vi.mock('./lib/supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(() => Promise.resolve({ data: { session: null } })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
    },
  },
}));

describe('App', () => {
  it('renders home page components by default', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('navbar')).toBeInTheDocument();
      expect(screen.getByTestId('noise-overlay')).toBeInTheDocument();
      expect(screen.getByTestId('hero')).toBeInTheDocument();
      expect(screen.getByTestId('features')).toBeInTheDocument();
      expect(screen.getByTestId('philosophy')).toBeInTheDocument();
      expect(screen.getByTestId('protocol')).toBeInTheDocument();
      expect(screen.getByTestId('cta')).toBeInTheDocument();
      expect(screen.getByTestId('footer')).toBeInTheDocument();
    });
  });

  it('fetches session on mount', async () => {
    render(<App />);

    await waitFor(() => {
      expect(supabase.auth.getSession).toHaveBeenCalled();
      expect(supabase.auth.onAuthStateChange).toHaveBeenCalled();
    });
  });
});
