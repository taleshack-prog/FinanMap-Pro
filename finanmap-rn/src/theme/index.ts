// FinanMap Pro — Design Tokens
// Fiel ao visual clean/moderno do HTML (Nubank-inspired)

export const Colors = {
  // Primária
  purple:     '#7C3AED',
  purpleLight:'#EDE9FE',
  purpleMid:  '#DDD6FE',
  purpleDark: '#5B21B6',

  // Semânticas
  green:      '#059669',
  greenLight: '#D1FAE5',
  amber:      '#D97706',
  amberLight: '#FEF3C7',
  red:        '#DC2626',
  redLight:   '#FEE2E2',
  blue:       '#2563EB',
  blueLight:  '#DBEAFE',

  // Neutros
  text:       '#0F172A',
  text2:      '#475569',
  text3:      '#94A3B8',
  text4:      '#CBD5E1',
  bg:         '#F8FAFC',
  surface:    '#FFFFFF',
  border:     '#E2E8F0',

  // DNA dos Genes
  gene: {
    renda_fixa:    '#7C3AED',
    renda_var:     '#2563EB',
    internacional: '#059669',
    cripto:        '#D97706',
  },
};

export const Typography = {
  // Tamanhos
  xs:   10,
  sm:   12,
  base: 14,
  md:   16,
  lg:   18,
  xl:   22,
  xxl:  28,
  hero: 40,

  // Pesos
  regular: '400' as const,
  medium:  '500' as const,
  semibold:'600' as const,
  bold:    '700' as const,
  black:   '800' as const,

  // Famílias (carregadas via expo-font)
  body:  'Outfit_400Regular',
  bold_: 'Outfit_700Bold',
  black_:'Outfit_800ExtraBold',
  mono:  'JetBrainsMono_400Regular',
  monoB: 'JetBrainsMono_500Medium',
};

export const Spacing = {
  xs:  4,
  sm:  8,
  md:  12,
  lg:  16,
  xl:  20,
  xxl: 24,
  xxxl:32,
};

export const Radii = {
  sm:  8,
  md:  12,
  lg:  16,
  xl:  20,
  full:999,
};

export const Shadows = {
  sm: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07,
    shadowRadius: 3,
    elevation: 2,
  },
  md: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  lg: {
    shadowColor: '#7C3AED',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 20,
    elevation: 8,
  },
};
