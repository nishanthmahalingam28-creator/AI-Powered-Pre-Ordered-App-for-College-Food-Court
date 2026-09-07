tailwind.config = {
    theme: {
        extend: {
            colors: {
                kpr: {
                    blue: '#113377',
                    teal: '#008080',
                    green: '#33AA44',
                    lightBg: '#f4f7f9',
                    facultyBlue: '#0052cc'
                },
                'kpr-blue': '#0c4a6e',
                'kpr-green': '#10b981'
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif']
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0', transform: 'translateY(-8px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' }
                }
            },
            animation: {
                fadeIn: 'fadeIn 0.2s ease-out forwards'
            }
        }
    }
};
