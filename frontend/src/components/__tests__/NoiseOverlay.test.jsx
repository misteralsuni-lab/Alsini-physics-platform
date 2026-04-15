import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import NoiseOverlay from '../NoiseOverlay';

describe('NoiseOverlay', () => {
  it('renders SVG with noise filter', () => {
    const { container } = render(<NoiseOverlay />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();

    const filter = container.querySelector('filter#noiseFilter');
    expect(filter).toBeInTheDocument();

    const turbulence = container.querySelector('feTurbulence');
    expect(turbulence).toBeInTheDocument();
  });
});
