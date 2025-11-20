"use client";

import { useEffect, useState, useRef, useCallback } from 'react';

export interface WebSocketMessage {
    type: string;
    data?: any;
    timestamp?: string;
    message?: string;
}

export function useWebSocket(url: string) {
    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [opportunities, setOpportunities] = useState<any[]>([]);
    const [metrics, setMetrics] = useState<any>({});

    const ws = useRef<WebSocket | null>(null);
    const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttempts = useRef(0);

    const connect = useCallback(() => {
        try {
            // Close existing connection if any
            if (ws.current) {
                ws.current.close();
            }

            ws.current = new WebSocket(url);

            ws.current.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
                reconnectAttempts.current = 0;
            };

            ws.current.onmessage = (event) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data);
                    setLastMessage(message);

                    // Handle different message types
                    if (message.type === 'opportunities' && message.data) {
                        setOpportunities(message.data);
                    } else if (message.type === 'metrics' && message.data) {
                        setMetrics(message.data);
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            ws.current.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.current.onclose = () => {
                console.log('WebSocket disconnected');
                setIsConnected(false);

                // Auto-reconnect with exponential backoff
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
                reconnectAttempts.current += 1;

                reconnectTimeout.current = setTimeout(() => {
                    console.log(`Reconnecting... (attempt ${reconnectAttempts.current})`);
                    connect();
                }, delay);
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
        }
    }, [url]);

    useEffect(() => {
        connect();

        return () => {
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
            }
            if (ws.current) {
                ws.current.close();
            }
        };
    }, [connect]);

    const sendMessage = useCallback((message: any) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message));
        }
    }, []);

    return {
        isConnected,
        lastMessage,
        opportunities,
        metrics,
        sendMessage
    };
}
