import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Auth from '../Auth';

// Mock GSAP to prevent animation issues in jsdom
vi.mock('gsap', () => ({
  default: {
    fromTo: vi.fn(),
  },
}));

// Mock Supabase
vi.mock('../../lib/supabaseClient', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
      signUp: vi.fn(),
      resetPasswordForEmail: vi.fn(),
    },
  },
}));

describe('Auth', () => {
  const renderAuth = () => {
    render(
      <BrowserRouter>
        <Auth />
      </BrowserRouter>
    );
  };

  it('renders login form by default', () => {
    renderAuth();
    expect(screen.getByText('Student Login')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Email Address')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Login/i })).toBeInTheDocument();
  });

  it('switches to register form', () => {
    renderAuth();
    fireEvent.click(screen.getByText("Don't have an account? Create one"));
    expect(screen.getByText('Register Account')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create Account/i })).toBeInTheDocument();
  });

  it('switches to reset password form', () => {
    renderAuth();
    fireEvent.click(screen.getByText("Forgot Password?"));
    expect(screen.getByText('Reset Password')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Password')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send Recovery Link/i })).toBeInTheDocument();
  });

  it('toggles password visibility', () => {
    renderAuth();
    const passwordInput = screen.getByPlaceholderText('Password');
    expect(passwordInput).toHaveAttribute('type', 'password');

    // Find the button inside the password input wrapper
    const toggleButton = passwordInput.parentElement.querySelector('button');
    fireEvent.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'text');

    fireEvent.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });
});
