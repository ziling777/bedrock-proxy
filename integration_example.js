#!/usr/bin/env node
/**
 * JavaScript/Node.js integration example for Bedrock Nova Proxy
 * npm install openai
 */

const OpenAI = require('openai');

// Your Bedrock Nova Proxy configuration
const client = new OpenAI({
    baseURL: 'https://itw9z9jxai.execute-api.eu-north-1.amazonaws.com/prod/v1',
    apiKey: 'dummy' // Not used but required
});

async function exampleChat() {
    console.log('🤖 Regular Chat Completion:');
    
    try {
        const response = await client.chat.completions.create({
            model: 'gpt-4o-mini', // Maps to eu.amazon.nova-lite-v1:0
            messages: [
                { role: 'system', content: 'You are a helpful assistant.' },
                { role: 'user', content: 'Explain serverless computing in simple terms.' }
            ],
            max_tokens: 200,
            temperature: 0.7
        });
        
        console.log('Response:', response.choices[0].message.content);
        console.log('Tokens used:', response.usage);
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

async function exampleStreaming() {
    console.log('\n🌊 Streaming Response:');
    
    try {
        const stream = await client.chat.completions.create({
            model: 'gpt-4o-mini',
            messages: [
                { role: 'user', content: 'Count from 1 to 5 with explanations.' }
            ],
            stream: true,
            max_tokens: 150
        });
        
        for await (const chunk of stream) {
            if (chunk.choices[0]?.delta?.content) {
                process.stdout.write(chunk.choices[0].delta.content);
            }
        }
        console.log('\n');
        
    } catch (error) {
        console.error('Streaming error:', error.message);
    }
}

async function main() {
    console.log('🚀 Bedrock Nova Proxy JavaScript Integration Examples');
    console.log('='.repeat(60));
    
    await exampleChat();
    await exampleStreaming();
    
    console.log('✅ Integration examples completed!');
}

if (require.main === module) {
    main().catch(console.error);
}
