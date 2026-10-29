// axios throws on 4xx/5xx responses. Show the server's message when it sent one.
export const getErrorMessage = (error) =>
    error?.response?.data?.message || error?.message || 'Something went wrong. Please try again.'
