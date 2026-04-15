import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import UpdatePassword from '../UpdatePassword';
import { supabase } from '../../lib/supabaseClient';

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
      updateUser: vi.fn(),
    },
  },
}));

describe('UpdatePassword', () => {
  const renderUpdatePassword = () => {
    render(
      <BrowserRouter>
        <UpdatePassword />
      </BrowserRouter>
    );
  };

  it('renders update password form correctly', () => {
    renderUpdatePassword();
    expect(screen.getByText('Secure Update')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('New Password')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Confirm New Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Set New Password/i })).toBeInTheDocument();
  });

  it('shows error if passwords do not match', async () => {
    renderUpdatePassword();
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'different' } });
    fireEvent.click(screen.getByRole('button', { name: /Set New Password/i }));

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
  });

  it('shows error if password is too short', async () => {
    renderUpdatePassword();
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'short' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: /Set New Password/i }));

    expect(await screen.findByText('Password must be at least 6 characters long.')).toBeInTheDocument();
  });

  it('calls updateUser on submit with valid password', async () => {
    supabase.auth.updateUser.mockResolvedValueOnce({ error: null });

    renderUpdatePassword();
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /Set New Password/i }));

    await waitFor(() => {
      expect(supabase.auth.updateUser).toHaveBeenCalledWith({ password: 'password123' });
    });
    expect(await screen.findByText('Password updated successfully. Rerouting to dashboard...')).toBeInTheDocument();
  });
});
