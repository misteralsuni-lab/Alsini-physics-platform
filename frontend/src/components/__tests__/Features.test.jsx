import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Features from '../Features';

// Mock GSAP to prevent animation issues in jsdom
vi.mock('gsap', () => ({
  default: {
    context: vi.fn((cb) => {
      cb();
      return { revert: vi.fn() };
    }),
    timeline: vi.fn(() => ({
      set: vi.fn().mockReturnThis(),
      to: vi.fn().mockReturnThis(),
    })),
  },
}));

describe('Features', () => {
  it('renders section heading correctly', () => {
    render(<Features />);
    expect(screen.getByText(/Core Architecture/i)).toBeInTheDocument();
    expect(screen.getByText(/Interactive functional/i)).toBeInTheDocument();
  });

  it('renders all three feature titles', () => {
    render(<Features />);
    expect(screen.getByText('Structured Syllabus Mastery')).toBeInTheDocument();
    expect(screen.getByText('Interactive Learning')).toBeInTheDocument();
    expect(screen.getByText('FHEQ Level 7 Experience')).toBeInTheDocument();
  });
});
