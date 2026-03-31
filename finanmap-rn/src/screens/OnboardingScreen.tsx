/**
 * Tela de Onboarding — 6 perguntas, animações com Reanimated
 * Integra com POST /api/v1/onboarding/profile
 */

import React, { useState, useRef } from 'react';
import {
  View, Text, ScrollView, TextInput, TouchableOpacity,
  StyleSheet, Dimensions, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle,
  withSpring, withTiming, FadeInUp, FadeOutDown,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';

import { Colors, Typography, Spacing, Radii, Shadows } from '../../src/theme';
import { Button, ProgressBar, Card, AllocBar } from '../../src/components';
import ApiService, { OnboardingInput } from '../../src/services/api';
import { useStore } from '../../src/store';

const { width: W } = Dimensions.get('window');

// ── Dados das perguntas ───────────────────────────────────────────────────────

const STEPS = [
  { id: 'welcome' },
  {
    id: 'objetivo', num: '1 / 6',
    title: 'Qual é seu principal objetivo?',
    sub:   'Define a lógica de alocação e o FIRE Tracker.',
    opts: [
      { val: 'fire',        label: 'Independência Financeira (FIRE)', sub: 'Aposentadoria precoce', emoji: '🔥' },
      { val: 'crescimento', label: 'Crescimento patrimonial',         sub: 'Maximizar retorno',    emoji: '📈' },
      { val: 'renda',       label: 'Renda passiva',                   sub: 'Dividendos mensais',   emoji: '💰' },
      { val: 'reserva',     label: 'Segurança e reserva',             sub: 'Baixo risco',          emoji: '🛡️' },
    ],
  },
  {
    id: 'financeiro', num: '2 / 6',
    title: 'Sua situação financeira atual',
    sub:   'Calibra o FIRE Tracker e o Kelly Criterion.',
  },
  {
    id: 'reacao', num: '3 / 6',
    title: 'Como você reage a quedas no mercado?',
    sub:   'Baseado em VIX histórico e psicologia comportamental.',
    opts: [
      { val: 'vende',  label: 'Vendo tudo', sub: 'Score: baixo (0–30)',    emoji: '😨' },
      { val: 'espera', label: 'Espero recuperar', sub: 'Score: moderado',  emoji: '😐' },
      { val: 'compra', label: 'Compro mais', sub: 'Score: agressivo',       emoji: '😎' },
      { val: 'all-in', label: 'All-in! É oportunidade', sub: 'Score: 85+', emoji: '🔥' },
    ],
  },
  {
    id: 'experiencia', num: '4 / 6',
    title: 'Sua experiência com investimentos',
    sub:   'Ajusta a complexidade das recomendações da IA.',
    opts: [
      { val: 'iniciante',     label: 'Iniciante',     sub: 'Só poupança/CDB', emoji: '🌱' },
      { val: 'intermediario', label: 'Intermediário', sub: 'Tenho ações/FIIs', emoji: '📊' },
      { val: 'avancado',      label: 'Avançado',      sub: 'Opções/cripto',    emoji: '⚡' },
    ],
  },
  {
    id: 'horizonte', num: '5 / 6',
    title: 'Horizonte e preferências',
    sub:   'Define o Monte Carlo e o algoritmo genético.',
  },
  { id: 'resultado', num: '6 / 6' },
];

// ── Componente Principal ──────────────────────────────────────────────────────

export default function OnboardingScreen() {
  const [step, setStep]       = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState<any>(null);

  // Campos financeiros
  const [patrimonio, setPatrimonio] = useState('50000');
  const [aporte,     setAporte]     = useState('2000');
  const [despesas,   setDespesas]   = useState('5000');
  const [horizonte,  setHorizonte]  = useState(10);
  const [cripto,     setCripto]     = useState(true);

  const setUser   = useStore(s => s.setUser);
  const setResult_ = useStore(s => s.setOnboardingResult);

  const progress = step === 0 ? 0 : Math.round((step / 6) * 100);

  function select(key: string, val: string) {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setAnswers(a => ({ ...a, [key]: val }));
  }

  function isSelected(key: string, val: string) {
    return answers[key] === val;
  }

  async function next() {
    if (step < STEPS.length - 2) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      if (step === STEPS.length - 3) {
        await calcularPerfil();
      } else {
        setStep(s => s + 1);
      }
    } else {
      finalizarOnboarding();
    }
  }

  function back() {
    if (step > 0) setStep(s => s - 1);
  }

  async function calcularPerfil() {
    setLoading(true);
    try {
      const payload: OnboardingInput = {
        objetivo:         (answers.objetivo || 'fire') as any,
        reacao_queda:     (answers.reacao   || 'espera') as any,
        experiencia:      (answers.experiencia || 'intermediario') as any,
        horizonte_anos:   horizonte,
        incluir_cripto:   cripto,
        patrimonio_atual: parseFloat(patrimonio) || 50000,
        aporte_mensal:    parseFloat(aporte)     || 2000,
        despesas_mensais: parseFloat(despesas)   || 5000,
      };
      const r = await ApiService.calcularPerfil(payload);
      setResult(r);
      setResult_(r);
      setUser({
        perfil:         r.perfil,
        score:          r.score_risco,
        patrimonio:     parseFloat(patrimonio) || 50000,
        aporte:         parseFloat(aporte)     || 2000,
        despesas:       parseFloat(despesas)   || 5000,
        horizonte,
        incluirCripto:  cripto,
        alloc:          r.alocacao_kelly,
        onboardingDone: true,
      });
      setStep(s => s + 1);
    } catch (e: any) {
      // Fallback local se API offline
      const score = calcScoreLocal();
      const fallback = buildFallback(score);
      setResult(fallback);
      setResult_(fallback);
      setUser({ perfil: fallback.perfil, score, onboardingDone: true,
        patrimonio: parseFloat(patrimonio)||50000,
        aporte: parseFloat(aporte)||2000,
        despesas: parseFloat(despesas)||5000,
        horizonte, incluirCripto: cripto, alloc: fallback.alocacao_kelly });
      setStep(s => s + 1);
    } finally {
      setLoading(false);
    }
  }

  function calcScoreLocal() {
    const rMap: Record<string,number> = { vende:10, espera:35, compra:65, 'all-in':90 };
    const eMap: Record<string,number> = { iniciante:0, intermediario:10, avancado:20 };
    const oMap: Record<string,number> = { fire:5, crescimento:10, renda:0, reserva:-10 };
    let s = (rMap[answers.reacao]||35) + (eMap[answers.experiencia]||0) + (oMap[answers.objetivo]||0);
    return Math.max(10, Math.min(100, s));
  }

  function buildFallback(score: number) {
    const perfil = score<30?'conservador': score<55?'moderado': score<75?'moderado_agressivo':'agressivo';
    const allocs: Record<string,Record<string,number>> = {
      conservador:        { renda_fixa:70, renda_var:20, internacional:10, cripto:0 },
      moderado:           { renda_fixa:50, renda_var:30, internacional:15, cripto:5 },
      moderado_agressivo: { renda_fixa:35, renda_var:30, internacional:15, cripto:20 },
      agressivo:          { renda_fixa:20, renda_var:30, internacional:15, cripto:35 },
    };
    const dp = parseFloat(despesas)||5000;
    const ap = parseFloat(aporte)||2000;
    const pt = parseFloat(patrimonio)||50000;
    const meta = dp*25*12;
    const anos = Math.log(meta/Math.max(pt,1)) / Math.log(1+(score/100*0.12));
    return {
      score_risco: score, perfil,
      alocacao_kelly: allocs[perfil],
      fire_anos_p50: Math.max(1, anos),
      fire_anos_p90: Math.max(1, anos*1.45),
      fire_meta_r: meta,
      fire_prob_sucesso: Math.min(95, 70+(score-50)*0.2),
      sharpe_esperado: score>75?2.1: score>55?1.82: score>30?1.45:1.2,
      sigma: score>75?0.22: score>55?0.18:0.14,
      descricao_perfil: 'Perfil calculado localmente.',
    };
  }

  function finalizarOnboarding() {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    router.replace('/(tabs)/dashboard');
  }

  const current = STEPS[step];

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.container}>

        {/* Header */}
        <View style={styles.header}>
          <View style={styles.logoRow}>
            <View style={styles.logoIcon}>
              <Text style={{ fontSize: 18 }}>💎</Text>
            </View>
            <Text style={styles.logoText}>Finan<Text style={{ color: Colors.purple }}>Map</Text> Pro</Text>
          </View>
          <Text style={styles.stepInfo}>
            {step === 0 ? 'Bem-vindo' : step === STEPS.length - 1 ? 'Seu Perfil' : `Pergunta ${step} de 5`}
          </Text>
        </View>

        <ProgressBar progress={progress} style={{ borderRadius: 0 }} height={3} />

        <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>

          {/* WELCOME */}
          {current.id === 'welcome' && (
            <Animated.View entering={FadeInUp.duration(400)} style={styles.welcome}>
              <LinearGradient colors={[Colors.purple, Colors.purpleDark]} style={styles.welcomeIcon}>
                <Text style={{ fontSize: 44 }}>💎</Text>
              </LinearGradient>
              <Text style={styles.welcomeTitle}>Bem-vindo ao FinanMap Pro</Text>
              <Text style={styles.welcomeSub}>
                Copiloto de investimentos com IA darwiniana, Monte Carlo e Kelly Criterion. Leva 2 minutos.
              </Text>
              <View style={styles.featureGrid}>
                {[
                  { emoji:'🧬', t:'IA Darwiniana',  s:'Algoritmo genético evolui robôs investidores' },
                  { emoji:'🎲', t:'Monte Carlo',    s:'10.000 simulações para calcular seu FIRE' },
                  { emoji:'📐', t:'Kelly Criterion',s:'Alocação ótima f*=(mu-rf)/sigma²' },
                  { emoji:'🔥', t:'FIRE Tracker',   s:'25× despesas · Regra dos 4%' },
                ].map(f => (
                  <View key={f.t} style={styles.featureItem}>
                    <View style={styles.featureEmoji}><Text style={{ fontSize: 20 }}>{f.emoji}</Text></View>
                    <Text style={styles.featureTitle}>{f.t}</Text>
                    <Text style={styles.featureSub}>{f.s}</Text>
                  </View>
                ))}
              </View>
            </Animated.View>
          )}

          {/* OPÇÕES (objetivo / reacao / experiencia) */}
          {(current.id === 'objetivo' || current.id === 'reacao' || current.id === 'experiencia') && (
            <Animated.View entering={FadeInUp.duration(350)}>
              <View style={styles.qBadge}><Text style={styles.qBadgeText}>{current.num}</Text></View>
              <Text style={styles.qTitle}>{current.title}</Text>
              <Text style={styles.qSub}>{current.sub}</Text>
              {(current as any).opts.map((opt: any) => (
                <TouchableOpacity
                  key={opt.val}
                  onPress={() => select(current.id, opt.val)}
                  activeOpacity={0.85}
                  style={[styles.option, isSelected(current.id, opt.val) && styles.optionSelected]}
                >
                  <View style={[styles.optEmoji, isSelected(current.id, opt.val) && { backgroundColor: Colors.purpleMid }]}>
                    <Text style={{ fontSize: 20 }}>{opt.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.optLabel, isSelected(current.id, opt.val) && { color: Colors.purpleDark }]}>
                      {opt.label}
                    </Text>
                    <Text style={styles.optSub}>{opt.sub}</Text>
                  </View>
                  {isSelected(current.id, opt.val) && (
                    <View style={styles.optCheck}><Text style={{ color: Colors.purple, fontSize: 16 }}>✓</Text></View>
                  )}
                </TouchableOpacity>
              ))}
            </Animated.View>
          )}

          {/* FINANCEIRO */}
          {current.id === 'financeiro' && (
            <Animated.View entering={FadeInUp.duration(350)}>
              <View style={styles.qBadge}><Text style={styles.qBadgeText}>{current.num}</Text></View>
              <Text style={styles.qTitle}>{current.title}</Text>
              <Text style={styles.qSub}>{current.sub}</Text>
              {[
                { label:'Patrimônio investido atual', val:patrimonio, set:setPatrimonio },
                { label:'Aporte mensal disponível',   val:aporte,     set:setAporte    },
                { label:'Despesas mensais',           val:despesas,   set:setDespesas  },
              ].map(f => (
                <View key={f.label} style={styles.field}>
                  <Text style={styles.fieldLabel}>{f.label}</Text>
                  <View style={styles.fieldInput}>
                    <Text style={styles.fieldPrefix}>R$</Text>
                    <TextInput
                      value={f.val}
                      onChangeText={f.set}
                      keyboardType="numeric"
                      style={styles.fieldText}
                      placeholderTextColor={Colors.text3}
                    />
                  </View>
                </View>
              ))}
            </Animated.View>
          )}

          {/* HORIZONTE */}
          {current.id === 'horizonte' && (
            <Animated.View entering={FadeInUp.duration(350)}>
              <View style={styles.qBadge}><Text style={styles.qBadgeText}>{current.num}</Text></View>
              <Text style={styles.qTitle}>{current.title}</Text>
              <Text style={styles.qSub}>{current.sub}</Text>

              <Card style={{ marginBottom: Spacing.lg }}>
                <Text style={styles.sliderLabel}>Horizonte FIRE</Text>
                <Text style={styles.sliderVal}>{horizonte} anos</Text>
                <View style={styles.sliderRow}>
                  {[3,5,8,10,15,20,25,30,35].map(v => (
                    <TouchableOpacity key={v} onPress={() => { setHorizonte(v); Haptics.selectionAsync(); }}
                      style={[styles.sliderPill, horizonte===v && styles.sliderPillActive]}>
                      <Text style={[styles.sliderPillText, horizonte===v && { color: Colors.purple }]}>{v}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </Card>

              <Text style={[styles.fieldLabel, { marginBottom: Spacing.sm }]}>Incluir cripto na carteira?</Text>
              <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
                {[
                  { val: true,  label: '₿ Sim — BTC/ETH staking 8–15%' },
                  { val: false, label: '🏦 Não — só ativos tradicionais' },
                ].map(opt => (
                  <TouchableOpacity key={String(opt.val)}
                    onPress={() => { setCripto(opt.val); Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); }}
                    style={[styles.option, { flex: 1 }, cripto===opt.val && styles.optionSelected]}
                  >
                    <Text style={[styles.optLabel, { fontSize: Typography.sm }, cripto===opt.val && { color: Colors.purpleDark }]}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </Animated.View>
          )}

          {/* RESULTADO */}
          {current.id === 'resultado' && result && (
            <Animated.View entering={FadeInUp.duration(400)}>
              <LinearGradient colors={[Colors.purple, Colors.purpleDark]} style={styles.scoreCard}>
                <Text style={styles.scoreNum}>{result.score_risco}</Text>
                <Text style={styles.scoreLabel}>Score VIX-adjusted</Text>
                <Text style={styles.scorePerfil}>{result.perfil.replace('_', '-')}</Text>
                <Text style={styles.scoreSub}>Sharpe esperado: {result.sharpe_esperado?.toFixed(2)} · σ: {(result.sigma*100)?.toFixed(0)}%</Text>
              </LinearGradient>

              <View style={styles.scoreStats}>
                {[
                  { l:'Anos FIRE (p50)', v:result.fire_anos_p50?.toFixed(1)+'a', c:Colors.purple },
                  { l:'Meta patrimonial', v:'R$'+Math.round((result.fire_meta_r||0)/1000)+'k', c:Colors.amber },
                  { l:'Prob. sucesso', v:(result.fire_prob_sucesso||0).toFixed(1)+'%', c:Colors.green },
                ].map(s => (
                  <View key={s.l} style={styles.scoreStat}>
                    <Text style={[styles.scoreStatVal, { color: s.c }]}>{s.v}</Text>
                    <Text style={styles.scoreStatLabel}>{s.l}</Text>
                  </View>
                ))}
              </View>

              <Card style={{ marginBottom: Spacing.lg }}>
                <Text style={[styles.fieldLabel, { marginBottom: Spacing.md }]}>Alocação Kelly Criterion</Text>
                {Object.entries(result.alocacao_kelly || {}).filter(([,v])=>(v as number)>0).map(([k,v]) => {
                  const colors = Colors.gene as Record<string,string>;
                  return (
                    <View key={k} style={styles.allocRow}>
                      <View style={[styles.allocDot, { backgroundColor: colors[k]||Colors.purple }]} />
                      <Text style={styles.allocName}>{k.replace('_',' ')}</Text>
                      <View style={styles.allocTrack}>
                        <View style={{ width: `${v}%`, height: 4, borderRadius: 2, backgroundColor: colors[k]||Colors.purple }} />
                      </View>
                      <Text style={styles.allocPct}>{v as number}%</Text>
                    </View>
                  );
                })}
              </Card>
            </Animated.View>
          )}

        </ScrollView>

        {/* Nav */}
        <View style={styles.nav}>
          {step > 0 && step < STEPS.length - 1 && (
            <TouchableOpacity onPress={back} style={styles.backBtn}>
              <Text style={styles.backText}>← Voltar</Text>
            </TouchableOpacity>
          )}
          <Button
            label={step === 0 ? 'Começar →' : step === STEPS.length - 2 ? 'Calcular meu perfil →' : step === STEPS.length - 1 ? 'Acessar o FinanMap Pro →' : 'Continuar →'}
            onPress={next}
            loading={loading}
            style={{ flex: 1 }}
          />
        </View>

      </View>
    </KeyboardAvoidingView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:      { flex:1, backgroundColor:Colors.surface },
  header:         { flexDirection:'row', alignItems:'center', justifyContent:'space-between', padding:Spacing.lg, borderBottomWidth:1, borderColor:Colors.border },
  logoRow:        { flexDirection:'row', alignItems:'center', gap:Spacing.sm },
  logoIcon:       { width:34, height:34, borderRadius:10, backgroundColor:Colors.purple, alignItems:'center', justifyContent:'center' },
  logoText:       { fontSize:Typography.md, fontWeight:Typography.black, color:Colors.text },
  stepInfo:       { fontSize:Typography.sm, color:Colors.text3 },

  body:           { padding:Spacing.xl, paddingBottom:Spacing.xxxl },
  welcome:        { alignItems:'center' },
  welcomeIcon:    { width:80, height:80, borderRadius:22, alignItems:'center', justifyContent:'center', marginBottom:Spacing.xl, marginTop:Spacing.lg },
  welcomeTitle:   { fontSize:Typography.xxl, fontWeight:Typography.black, color:Colors.text, textAlign:'center', marginBottom:Spacing.sm },
  welcomeSub:     { fontSize:Typography.base, color:Colors.text2, textAlign:'center', lineHeight:22, marginBottom:Spacing.xxl },
  featureGrid:    { flexDirection:'row', flexWrap:'wrap', gap:Spacing.sm, width:'100%' },
  featureItem:    { width:(W-Spacing.xl*2-Spacing.sm)/2, backgroundColor:Colors.bg, borderRadius:Radii.md, padding:Spacing.md },
  featureEmoji:   { marginBottom:Spacing.xs },
  featureTitle:   { fontSize:Typography.sm, fontWeight:Typography.bold, color:Colors.text, marginBottom:2 },
  featureSub:     { fontSize:Typography.xs, color:Colors.text3, lineHeight:15 },

  qBadge:         { backgroundColor:Colors.purpleLight, alignSelf:'flex-start', paddingHorizontal:Spacing.sm, paddingVertical:3, borderRadius:Radii.full, marginBottom:Spacing.md },
  qBadgeText:     { fontSize:Typography.xs, fontWeight:Typography.bold, color:Colors.purpleDark, textTransform:'uppercase', letterSpacing:0.6 },
  qTitle:         { fontSize:Typography.xl, fontWeight:Typography.bold, color:Colors.text, marginBottom:Spacing.xs },
  qSub:           { fontSize:Typography.base, color:Colors.text2, marginBottom:Spacing.xl },

  option:         { flexDirection:'row', alignItems:'center', gap:Spacing.md, padding:Spacing.md, borderWidth:1.5, borderColor:Colors.border, borderRadius:Radii.md, marginBottom:Spacing.sm, backgroundColor:Colors.surface },
  optionSelected: { borderColor:Colors.purple, backgroundColor:Colors.purpleLight },
  optEmoji:       { width:40, height:40, borderRadius:Radii.sm, backgroundColor:Colors.bg, alignItems:'center', justifyContent:'center' },
  optLabel:       { fontSize:Typography.base, fontWeight:Typography.semibold, color:Colors.text },
  optSub:         { fontSize:Typography.xs, color:Colors.text3, marginTop:2 },
  optCheck:       { width:28, height:28, borderRadius:14, backgroundColor:Colors.purpleLight, alignItems:'center', justifyContent:'center' },

  field:          { marginBottom:Spacing.lg },
  fieldLabel:     { fontSize:Typography.sm, fontWeight:Typography.semibold, color:Colors.text2, marginBottom:Spacing.xs },
  fieldInput:     { flexDirection:'row', alignItems:'center', borderWidth:1.5, borderColor:Colors.border, borderRadius:Radii.md, paddingHorizontal:Spacing.md, height:50 },
  fieldPrefix:    { fontSize:Typography.base, fontWeight:Typography.bold, color:Colors.text3, marginRight:Spacing.xs },
  fieldText:      { flex:1, fontSize:Typography.md, fontWeight:Typography.semibold, color:Colors.text },

  sliderLabel:    { fontSize:Typography.sm, color:Colors.text2, fontWeight:Typography.semibold, marginBottom:4 },
  sliderVal:      { fontSize:Typography.xxl, fontWeight:Typography.black, color:Colors.purple, marginBottom:Spacing.md },
  sliderRow:      { flexDirection:'row', flexWrap:'wrap', gap:Spacing.xs },
  sliderPill:     { paddingHorizontal:Spacing.md, paddingVertical:Spacing.xs, borderRadius:Radii.full, borderWidth:1, borderColor:Colors.border, backgroundColor:Colors.bg },
  sliderPillActive:{ borderColor:Colors.purple, backgroundColor:Colors.purpleLight },
  sliderPillText: { fontSize:Typography.sm, color:Colors.text2, fontWeight:Typography.medium },

  scoreCard:      { borderRadius:Radii.xl, padding:Spacing.xxl, alignItems:'center', marginBottom:Spacing.lg },
  scoreNum:       { fontSize:72, fontWeight:Typography.black, color:'white', lineHeight:80 },
  scoreLabel:     { fontSize:Typography.sm, color:'rgba(255,255,255,.75)', marginBottom:Spacing.xs },
  scorePerfil:    { fontSize:Typography.xl, fontWeight:Typography.bold, color:'white', marginBottom:4 },
  scoreSub:       { fontSize:Typography.sm, color:'rgba(255,255,255,.65)' },
  scoreStats:     { flexDirection:'row', gap:Spacing.sm, marginBottom:Spacing.lg },
  scoreStat:      { flex:1, backgroundColor:Colors.bg, borderRadius:Radii.md, padding:Spacing.md, alignItems:'center' },
  scoreStatVal:   { fontSize:Typography.lg, fontWeight:Typography.black },
  scoreStatLabel: { fontSize:Typography.xs, color:Colors.text3, marginTop:4, textAlign:'center' },

  allocRow:       { flexDirection:'row', alignItems:'center', gap:Spacing.sm, marginBottom:Spacing.sm },
  allocDot:       { width:10, height:10, borderRadius:3 },
  allocName:      { flex:1, fontSize:Typography.sm, color:Colors.text2 },
  allocTrack:     { width:90, height:4, backgroundColor:Colors.bg, borderRadius:2 },
  allocPct:       { fontSize:Typography.sm, fontWeight:Typography.bold, minWidth:32, textAlign:'right', fontVariant:['tabular-nums'] },

  nav:            { flexDirection:'row', gap:Spacing.sm, padding:Spacing.lg, borderTopWidth:1, borderColor:Colors.border, backgroundColor:Colors.surface },
  backBtn:        { paddingHorizontal:Spacing.lg, paddingVertical:Spacing.md, borderWidth:1, borderColor:Colors.border, borderRadius:Radii.md, justifyContent:'center' },
  backText:       { fontSize:Typography.base, color:Colors.text2, fontWeight:Typography.semibold },
});
