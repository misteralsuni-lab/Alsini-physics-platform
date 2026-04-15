import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Footer from '../Footer';

describe('Footer', () => {
  it('renders the brand name', () => {
    render(<Footer />);
    expect(screen.getByText('EDU-VLE')).toBeInTheDocument();
  });

  it('renders the description', () => {
    render(<Footer />);
    expect(screen.getByText(/A premium, open-access virtual learning environment/i)).toBeInTheDocument();
  });

  it('renders system status', () => {
    render(<Footer />);
    expect(screen.getByText('System Operational')).toBeInTheDocument();
  });

  it('renders navigation sections', () => {
    render(<Footer />);
    expect(screen.getByText('Navigation')).toBeInTheDocument();
    expect(screen.getByText('Community & Legal')).toBeInTheDocument();
  });

  it('renders the copyright text with the current year', () => {
    render(<Footer />);
    const currentYear = new Date().getFullYear();
    expect(screen.getByText(new RegExp(`© ${currentYear} EDU-VLE`))).toBeInTheDocument();
  });
});
