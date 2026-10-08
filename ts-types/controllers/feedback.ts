export interface FeedbackContext {
    endpoint: string;
}

export interface FeedbackFailurePayload {
    errors?: Array<{ message: string }>;
}
