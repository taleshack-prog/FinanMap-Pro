/**
 * Dashboard — tela principal do app
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, RefreshControl, Dimensions,
} from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';

import { Colors, Typography, Spacing, Radii, Shadows } from '../theme';
import { Card, MetricCard, SectionHeader, ProgressBar, Chip, AllocBar, LiveDot } from '../components';
import ApiService from '../services/api';
import { useStore } from '../store';

const { width: W } = Dimensions.get('window');

export default function DashboardScreen() {
  const user   = useStore(s => s.user);
  const onb    = useStore(s => s.onboardingResult);
  const fire   = useStore(s => s.fireResult);
  const market = useStore(s => s.marketData);
  const setFire   = useStore(s => s.setFireResult);
  const setMarket = useStore(s => s.setMarketData);

  const [refreshing, setRefreshing] = useState(false);

  const pat      = user?.patrimonio || 50000;
  const aporte   = user?.aporte     || 2000;
  const desp     = user?.despesas   || 5000;
  const meta     = desp * 25 * 12;
  const progress = Math.min(100, Math.round(pat / meta * 100));
  const fireAnos = onb?.fire_anos_p50 || fire?.anos_para_fire || 8.3;
  const alloc    = user?.alloc || onb?.alocacao_kelly || {};
  const geneColors = Colors.gene as Record<string,string>;

  async function load(){
    try {
      const [fireRes, mkt] = await Promise.allSettled([
        ApiService.calcularFire({ aporte_mensal:aporte, despesas_mensais:desp, patrimonio_atual:pat }),
        ApiService.getDadosMercado(),
      ]);
      if(fireRes.status==='fulfilled') setFire(fireRes.value);
      if(mkt.status==='fulfilled')     setMarket(mkt.value);
    } catch {}
  }

  async function onRefresh(){
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  useEffect(()=>{ load(); },[]);

  return (
    <ScrollView
      style={styles.container}
      showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.purple}/>}
    >
      {/* Header */}
      <Animated.View entering={FadeInUp.duration(400)} style={styles.header}>
        <LinearGradient colors={[Colors.purple, Colors.purpleDark]} style={styles.headerGradient}>
          <View style={styles.headerTop}>
            <View>
              <Text style={styles.headerGreet}>Olá, {user?.nome||'Investidor'} 👋</Text>
              <View style={{ flexDirection:'row', alignItems:'center', gap:Spacing.xs }}>
                <LiveDot color="rgba(255,255,255,.7)"/>
                <Text style={styles.headerSub}>Mercado aberto · yfinance 2026</Text>
              </View>
            </View>
            <View style={styles.profileBadge}>
              <Text style={styles.profileScore}>{user?.score||72}</Text>
              <Text style={styles.profileLabel}>score</Text>
            </View>
          </View>

          <View style={styles.headerPat}>
            <Text style={styles.headerPatLabel}>Patrimônio total</Text>
            <Text style={styles.headerPatValue}>R${pat.toLocaleString('pt-BR')}</Text>
            <Text style={styles.headerPatSub}>↑ +R$3.840 este mês · +18,4% a.a.</Text>
          </View>
        </LinearGradient>
      </Animated.View>

      {/* Métricas */}
      <View style={styles.metricsRow}>
        <MetricCard label="Rentab. 12m"   value="18,4%"               accent={Colors.green}  style={{flex:1}} sub="↑ vs IBOV 12,1%"  subColor={Colors.green}/>
        <MetricCard label="Aporte mensal" value={'R$'+aporte.toLocaleString('pt-BR')} accent={Colors.amber}  style={{flex:1}} sub={`de R${(aporte+2000).toLocaleString('pt-BR')}/meta`}/>
        <MetricCard label="Sharpe"        value={(onb?.sharpe_esperado||1.82).toFixed(2)} accent={Colors.blue} style={{flex:1}} sub="vs BOVA11: 0,91"/>
      </View>

      {/* FIRE card */}
      <Animated.View entering={FadeInUp.delay(100).duration(400)} style={styles.section}>
        <Card>
          <View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', marginBottom:Spacing.xs }}>
            <SectionHeader title="FIRE Tracker" sub="Meta: 25× despesas · Regra dos 4%" />
            <Chip label={`~${fireAnos.toFixed(1)} anos`} bg={Colors.amberLight} color="#92400E"/>
          </View>
          <ProgressBar progress={progress} style={{ marginBottom:Spacing.xs }}/>
          <View style={{ flexDirection:'row', justifyContent:'space-between', marginBottom:Spacing.lg }}>
            <Text style={styles.fireLabel}>R${Math.round(pat/1000)}k atual</Text>
            <Text style={styles.firePct}>{progress}% completo</Text>
            <Text style={styles.fireLabel}>Meta: R${Math.round(meta/1000)}k</Text>
          </View>
          <View style={styles.fireStats}>
            {[
              { l:'Patrimônio',   v:'R$'+Math.round(pat/1000)+'k',              c:Colors.purple },
              { l:'Projeção p90', v:((onb?.fire_anos_p90||fire?.monte_carlo?.anos_p90||12.1)).toFixed(1)+'a', c:Colors.amber },
              { l:'Taxa retirada',v:'4,0%',                                      c:Colors.text },
              { l:'Prob. sucesso',v:((onb?.fire_prob_sucesso||fire?.monte_carlo?.prob_sucesso_pct||87)).toFixed(0)+'%', c:Colors.green },
            ].map(s=>(
              <View key={s.l} style={styles.fireStat}>
                <Text style={styles.fireStatLabel}>{s.l}</Text>
                <Text style={[styles.fireStatVal, { color:s.c }]}>{s.v}</Text>
              </View>
            ))}
          </View>
        </Card>
      </Animated.View>

      {/* Alocação + market */}
      <Animated.View entering={FadeInUp.delay(150).duration(400)} style={styles.section}>
        <View style={{ flexDirection:'row', gap:Spacing.sm }}>
          <Card style={{ flex:1.6 }}>
            <SectionHeader title="Alocação Kelly" sub="Algoritmo genético otimizado" />
            <View style={{ gap:Spacing.sm }}>
              {Object.entries(alloc).filter(([,v])=>(v as number)>0).map(([k,v])=>(
                <View key={k} style={{ flexDirection:'row', alignItems:'center', gap:Spacing.sm }}>
                  <View style={{ width:10, height:10, borderRadius:2, backgroundColor:geneColors[k]||Colors.purple }}/>
                  <Text style={{ flex:1, fontSize:Typography.sm, color:Colors.text2 }}>{k.replace('_',' ')}</Text>
                  <View style={{ width:70, height:4, backgroundColor:Colors.bg, borderRadius:2 }}>
                    <View style={{ width:`${v}%`, height:4, borderRadius:2, backgroundColor:geneColors[k]||Colors.purple }}/>
                  </View>
                  <Text style={{ fontSize:Typography.sm, fontWeight:Typography.bold, minWidth:30, textAlign:'right' }}>{v}%</Text>
                </View>
              ))}
            </View>
            <View style={{ marginTop:Spacing.md, flexDirection:'row', justifyContent:'space-between' }}>
              <View><Text style={{ fontSize:Typography.xs, color:Colors.text3 }}>Sharpe</Text><Text style={{ fontSize:Typography.lg, fontWeight:Typography.black, color:Colors.purple }}>{(onb?.sharpe_esperado||1.82).toFixed(2)}</Text></View>
              <View><Text style={{ fontSize:Typography.xs, color:Colors.text3 }}>Sortino</Text><Text style={{ fontSize:Typography.lg, fontWeight:Typography.black, color:Colors.green }}>2,14</Text></View>
            </View>
          </Card>

          <Card style={{ flex:1 }}>
            <SectionHeader title="Mercado" sub="Ao vivo"/>
            {[
              { l:'IBOV',  v:market?.ibov?`${Math.round(market.ibov/1000)}k`:'130k',    c:Colors.text },
              { l:'Selic', v:(market?.selic||10.5)+'%',  c:Colors.green },
              { l:'BTC',   v:market?.btc_brl?`R$${Math.round(market.btc_brl/1000)}k`:'R$520k', c:Colors.amber },
              { l:'USD',   v:'R$'+(market?.dolar||5.15).toFixed(2), c:Colors.blue },
            ].map(m=>(
              <View key={m.l} style={{ flexDirection:'row', justifyContent:'space-between', paddingVertical:5, borderBottomWidth:1, borderColor:Colors.bg }}>
                <Text style={{ fontSize:Typography.xs, color:Colors.text3 }}>{m.l}</Text>
                <Text style={{ fontSize:Typography.xs, fontWeight:Typography.bold, color:m.c }}>{m.v}</Text>
              </View>
            ))}
          </Card>
        </View>
      </Animated.View>

      {/* CTA Robôs */}
      <Animated.View entering={FadeInUp.delay(200).duration(400)} style={[styles.section, { paddingBottom:Spacing.xxxl*2 }]}>
        <TouchableOpacity onPress={()=>router.push('/(tabs)/robots')} activeOpacity={0.9}>
          <LinearGradient colors={['#0F172A','#1E293B']} style={styles.robotsCta}>
            <View>
              <View style={styles.robotsCtaBadge}>
                <View style={{ width:6, height:6, borderRadius:3, backgroundColor:'#A78BFA' }}/>
                <Text style={styles.robotsCtaBadgeText}>Algoritmo Genético · Ativo</Text>
              </View>
              <Text style={styles.robotsCtaTitle}>Ver meus Robôs Investidores</Text>
              <Text style={styles.robotsCtaSub}>8 estratégias evoluindo · Sortino 2,14 · CAGR 18%</Text>
            </View>
            <Text style={{ fontSize:32 }}>🧬</Text>
          </LinearGradient>
        </TouchableOpacity>
      </Animated.View>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container:       { flex:1, backgroundColor:Colors.bg },
  header:          { marginBottom:0 },
  headerGradient:  { padding:Spacing.xl, paddingTop:Spacing.xxl },
  headerTop:       { flexDirection:'row', justifyContent:'space-between', alignItems:'flex-start', marginBottom:Spacing.xl },
  headerGreet:     { fontSize:Typography.xl, fontWeight:Typography.black, color:'white', marginBottom:4 },
  headerSub:       { fontSize:Typography.sm, color:'rgba(255,255,255,.65)' },
  profileBadge:    { alignItems:'center', backgroundColor:'rgba(255,255,255,.15)', borderRadius:Radii.md, padding:Spacing.sm },
  profileScore:    { fontSize:Typography.xxl, fontWeight:Typography.black, color:'white', lineHeight:32 },
  profileLabel:    { fontSize:Typography.xs, color:'rgba(255,255,255,.65)' },
  headerPat:       {},
  headerPatLabel:  { fontSize:Typography.sm, color:'rgba(255,255,255,.65)', marginBottom:4 },
  headerPatValue:  { fontSize:Typography.hero, fontWeight:Typography.black, color:'white', lineHeight:48 },
  headerPatSub:    { fontSize:Typography.sm, color:'rgba(255,255,255,.65)', marginTop:4 },

  metricsRow:      { flexDirection:'row', gap:Spacing.sm, padding:Spacing.xl, paddingBottom:0 },
  section:         { paddingHorizontal:Spacing.xl, paddingTop:Spacing.lg },

  fireLabel:       { fontSize:Typography.xs, color:Colors.text3 },
  firePct:         { fontSize:Typography.xs, fontWeight:Typography.bold, color:Colors.text2 },
  fireStats:       { flexDirection:'row', gap:Spacing.xs },
  fireStat:        { flex:1, backgroundColor:Colors.bg, borderRadius:Radii.sm, padding:Spacing.sm },
  fireStatLabel:   { fontSize:9, color:Colors.text3, textTransform:'uppercase', letterSpacing:.4, marginBottom:3 },
  fireStatVal:     { fontSize:Typography.base, fontWeight:Typography.black },

  robotsCta:       { borderRadius:Radii.xl, padding:Spacing.xl, flexDirection:'row', alignItems:'center', justifyContent:'space-between' },
  robotsCtaBadge:  { flexDirection:'row', alignItems:'center', gap:5, backgroundColor:'rgba(124,58,237,.3)', alignSelf:'flex-start', paddingHorizontal:Spacing.sm, paddingVertical:3, borderRadius:Radii.full, marginBottom:Spacing.sm },
  robotsCtaBadgeText:{ fontSize:Typography.xs, color:'#C4B5FD', fontWeight:Typography.bold },
  robotsCtaTitle:  { fontSize:Typography.md, fontWeight:Typography.black, color:'white', marginBottom:4 },
  robotsCtaSub:    { fontSize:Typography.sm, color:'rgba(255,255,255,.6)' },
});
