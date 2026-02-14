import React from 'react';
import './AnimatedBackground.css';

const AnimatedBackground = ({ intensity = 'normal' }) => {
    const opacityClass = intensity === 'subtle' ? 'bg-layer--subtle' : '';

    return (
        <div className={`bg-layer ${opacityClass}`} aria-hidden="true">
            {/* Mesh gradient base */}
            <div className="bg-mesh" />

            {/* Floating orbs */}
            <div className="bg-orb bg-orb--1" />
            <div className="bg-orb bg-orb--2" />
            <div className="bg-orb bg-orb--3" />
            <div className="bg-orb bg-orb--4" />

            {/* Aurora streaks */}
            <div className="bg-aurora" />
            <div className="bg-aurora bg-aurora--2" />

            {/* Noise grain overlay */}
            <div className="bg-grain" />
        </div>
    );
};

export default AnimatedBackground;
