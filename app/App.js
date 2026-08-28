import { useState, useRef } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

const BACKEND_URL = Platform.OS === 'web' ? '' : 'https://tradies.koroai.org';

const DISCLAIMER =
  "I'm the Tradie's Apprentice - not a licensed electrician or plumber. I carry real, " +
  'sourced knowledge across electrical, plumbing, tools, and DIY conversion topics, but ' +
  "if it touches the switchboard, gas, sewage, or mains supply, that needs a licensed " +
  'professional, not me.';

export default function App() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  const ask = async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    const userMessage = { role: 'user', text: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion('');
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Something went wrong.');
      }
      setMessages((prev) => [...prev, { role: 'apprentice', text: data.answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'error', text: `Couldn't get an answer: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <Text style={styles.title}>The Tradie's Apprentice</Text>
        <Text style={styles.disclaimer}>{DISCLAIMER}</Text>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.messages}
        >
          {messages.length === 0 && (
            <Text style={styles.empty}>
              Ask about electrical, plumbing, tools, or DIY conversions - e.g. "is it safe to
              fix my TV backlight myself?" or "how do I convert an e-bike with regen braking?"
            </Text>
          )}
          {messages.map((m, i) => (
            <View
              key={i}
              style={[
                styles.bubble,
                m.role === 'user' ? styles.userBubble : styles.apprenticeBubble,
                m.role === 'error' && styles.errorBubble,
              ]}
            >
              <Text style={m.role === 'user' ? styles.userText : styles.apprenticeText}>
                {m.text}
              </Text>
            </View>
          ))}
          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color="#b8791f" />
              <Text style={styles.loadingText}>Thinking, grounded in real sources...</Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Ask a question..."
            value={question}
            onChangeText={setQuestion}
            onSubmitEditing={ask}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} onPress={ask} disabled={loading}>
            <Text style={styles.sendButtonText}>Ask</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#faf6ef' },
  flex: { flex: 1 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e6dcc8',
  },
  title: { fontSize: 20, fontWeight: '700', color: '#2a2116' },
  disclaimer: { fontSize: 12, color: '#7a6a4f', marginTop: 6, lineHeight: 17 },
  messages: { padding: 16, paddingBottom: 24 },
  empty: { color: '#9a8a6a', fontSize: 14, marginTop: 24, textAlign: 'center' },
  bubble: { borderRadius: 12, padding: 12, marginBottom: 10, maxWidth: '90%' },
  userBubble: { backgroundColor: '#2a2116', alignSelf: 'flex-end' },
  apprenticeBubble: { backgroundColor: '#fff', alignSelf: 'flex-start', borderWidth: 1, borderColor: '#e6dcc8' },
  errorBubble: { backgroundColor: '#fbe4e4', borderColor: '#e0a0a0' },
  userText: { color: '#fff', fontSize: 15 },
  apprenticeText: { color: '#2a2116', fontSize: 15, lineHeight: 21 },
  loadingRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  loadingText: { color: '#7a6a4f', fontSize: 13 },
  inputRow: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#e6dcc8',
    backgroundColor: '#faf6ef',
    alignItems: 'flex-end',
  },
  input: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#e6dcc8',
    paddingHorizontal: 12,
    paddingVertical: 10,
    maxHeight: 120,
    fontSize: 15,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: '#b8791f',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  sendButtonText: { color: '#fff', fontWeight: '600' },
});
