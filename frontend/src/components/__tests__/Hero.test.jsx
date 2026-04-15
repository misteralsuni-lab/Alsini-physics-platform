import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Hero from '../Hero';

// Mock GSAP to prevent animation issues in jsdom
vi.mock('gsap', () => ({
  default: {
    context: vi.fn((cb) => {
      cb();
      return { revert: vi.fn() };
    }),
    from: vi.fn(),
  },
}));

describe('Hero', () => {
  it('renders heading texts', () => {
    render(<Hero />);
    expect(screen.getByText(/PHYSICS MASTERY BEYOND/i)).toBeInTheDocument();
    expect(screen.getByText(/limits./i)).toBeInTheDocument();
  });

  it('renders call to action buttons', () => {
    render(<Hero />);
    expect(screen.getByRole('button', { name: /Select Exam Route/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Explore Methodology/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Join Telegram Community/i })).toBeInTheDocument();
  });

  it('renders Telegram QR code section', () => {
    render(<Hero />);
    expect(screen.getByText(/Scan to Join/i)).toBeInTheDocument();
    const qrImage = screen.getByRole('img', { name: /EDU-VLE Telegram QR Code/i });
    expect(qrImage).toBeInTheDocument();
  });
});
