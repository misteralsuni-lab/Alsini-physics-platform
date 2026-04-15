import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Protocol from '../Protocol';

// Mock GSAP and ScrollTrigger
vi.mock('gsap', () => ({
  default: {
    registerPlugin: vi.fn(),
    context: vi.fn((cb) => {
      cb();
      return { revert: vi.fn() };
    }),
    to: vi.fn(),
    utils: {
      toArray: vi.fn(() => []),
    },
  },
}));

vi.mock('gsap/ScrollTrigger', () => ({
  ScrollTrigger: {
    create: vi.fn(),
  },
}));

describe('Protocol', () => {
  it('renders section heading', () => {
    render(<Protocol />);
    expect(screen.getByText('Methodology')).toBeInTheDocument();
    expect(screen.getByText('The Revision Protocol')).toBeInTheDocument();
  });

  it('renders protocol steps', () => {
    render(<Protocol />);
    expect(screen.getByText('01 //')).toBeInTheDocument();
    expect(screen.getByText('THE FOUNDATION')).toBeInTheDocument();

    expect(screen.getByText('02 //')).toBeInTheDocument();
    expect(screen.getByText('THE SYNTHESIS')).toBeInTheDocument();

    expect(screen.getByText('03 //')).toBeInTheDocument();
    expect(screen.getByText('THE APPLICATION')).toBeInTheDocument();
  });
});
