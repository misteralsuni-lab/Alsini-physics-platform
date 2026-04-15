import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Navbar from '../Navbar';

vi.mock('../../lib/supabaseClient', () => ({
  supabase: {
    auth: {
      signOut: vi.fn(),
    },
  },
}));

describe('Navbar', () => {
  const renderNavbar = (session = null) => {
    render(
      <BrowserRouter>
        <Navbar session={session} />
      </BrowserRouter>
    );
  };

  it('renders the logo', () => {
    renderNavbar();
    expect(screen.getByText('EDU-VLE')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    renderNavbar();
    const links = screen.getAllByRole('link');
    const linkTexts = links.map(l => l.textContent);
    expect(linkTexts).toContain('Dashboard');
    expect(linkTexts).toContain('My Courses');
    expect(linkTexts).toContain('Community');
    expect(linkTexts).toContain('Admin');
  });

  it('renders login button when no session', () => {
    renderNavbar();
    expect(screen.getByRole('button', { name: /Login/i })).toBeInTheDocument();
  });

  it('renders user email and logout button when session exists', () => {
    const session = { user: { email: 'test@example.com' } };
    renderNavbar(session);
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByTitle('Log Out')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Login/i })).not.toBeInTheDocument();
  });

  it('toggles mobile menu when menu button is clicked', () => {
    renderNavbar();

    // In mobile view (simulated by clicking button)
    const menuButtons = screen.getAllByRole('button');
    // The menu button is the last one on desktop view normally before mobile menu opens
    const toggleButton = menuButtons[menuButtons.length - 1];

    // There are 4 nav links in desktop by default, so we expect more when menu opens
    const initialLinkCount = screen.getAllByText('Dashboard').length;

    fireEvent.click(toggleButton);

    const openLinkCount = screen.getAllByText('Dashboard').length;
    expect(openLinkCount).toBeGreaterThan(initialLinkCount);
  });
});
