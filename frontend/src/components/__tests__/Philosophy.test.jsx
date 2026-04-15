import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Philosophy from '../Philosophy';

// Mock GSAP and ScrollTrigger
vi.mock('gsap', () => ({
  default: {
    registerPlugin: vi.fn(),
    context: vi.fn((cb) => {
      cb();
      return { revert: vi.fn() };
    }),
    to: vi.fn(),
    from: vi.fn(),
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {},
}));

describe('Philosophy', () => {
  it('renders philosophy texts', () => {
    render(<Philosophy />);
    expect(screen.getByText(/Most revision platforms focus on:/i)).toBeInTheDocument();
    expect(screen.getByText(/We focus on: deep/i)).toBeInTheDocument();
    expect(screen.getByText('mastery.')).toBeInTheDocument();
  });
});
