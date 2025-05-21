// frontend/src/resources/student/FaceRegistrationPage.js
import * as React from 'react';
import { useNotify, Button as RaButton, Loading, Title } from 'react-admin'; // RaButton for react-admin context if needed
import { Typography, Paper, Button, Box, Input, Alert } from '@mui/material';

export const FaceRegistrationPage = () => {
    const notify = useNotify();
    const [selectedFile, setSelectedFile] = React.useState(null);
    const [isLoading, setIsLoading] = React.useState(false);
    const [serverMessage, setServerMessage] = React.useState(null);
    const [serverMessageType, setServerMessageType] = React.useState('info'); // 'info', 'success', 'error'

    const handleFileChange = (event) => {
        setSelectedFile(event.target.files[0]);
        setServerMessage(null); // Clear previous messages
    };

    const handleRegisterFace = async () => {
        if (!selectedFile) {
            notify('Please select an image file first.', { type: 'warning' });
            setServerMessage('Please select an image file first.');
            setServerMessageType('warning');
            return;
        }

        setIsLoading(true);
        setServerMessage(null);
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const token = localStorage.getItem('token'); // Or use authProvider.getCredentials() if available
            if (!token) {
                throw new Error('Authentication token not found.');
            }

            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/users/me/register-face`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    // 'Content-Type': 'multipart/form-data' is set automatically by browser for FormData
                },
                body: formData,
            });

            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.detail || `HTTP error! status: ${response.status}`);
            }

            notify('Face registered successfully!', { type: 'success' });
            setServerMessage(responseData.message || 'Face registered successfully!');
            setServerMessageType('success');
            setSelectedFile(null); // Clear file input after success
            // Optionally clear the visual file input as well
            const fileInput = document.getElementById('face-image-input');
            if (fileInput) fileInput.value = '';


        } catch (error) {
            console.error('Face registration error:', error);
            notify(`Error: ${error.message}`, { type: 'error' });
            setServerMessage(error.message || 'An unexpected error occurred.');
            setServerMessageType('error');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Paper sx={{ p: 3, maxWidth: 600, margin: 'auto', mt: 4 }}>
            <Title title="Register Your Face" />
            <Typography variant="h5" gutterBottom sx={{ mb: 2, textAlign: 'center' }}>
                Face Registration for Attendance
            </Typography>
            <Typography variant="body1" sx={{ mb: 3, textAlign: 'center', color: 'text.secondary' }}>
                Upload a clear, front-facing picture of yourself. This image will be used to verify your attendance.
                Ensure only your face is visible in the picture.
            </Typography>

            {serverMessage && (
                <Alert severity={serverMessageType} sx={{ mb: 2, '.MuiAlert-message': { width: '100%' } }}> {/* Ensure message takes full width */}
                    {serverMessage}
                </Alert>
            )}

            <Box sx={{ mb: 3, p:2, border: '1px dashed grey', borderRadius: 1, textAlign: 'center' }}>
                <Input
                    type="file"
                    id="face-image-input"
                    accept="image/jpeg, image/png, image/jpg"
                    onChange={handleFileChange}
                    sx={{ display: 'none' }} // Hide default input
                />
                 <label htmlFor="face-image-input">
                    <Button variant="outlined" component="span" sx={{mb:1}}>
                        Choose Image
                    </Button>
                </label>
                {selectedFile && (
                    <Typography variant="caption" display="block">Selected file: {selectedFile.name}</Typography>
                )}
            </Box>

            <Button
                variant="contained"
                color="primary"
                onClick={handleRegisterFace}
                disabled={isLoading || !selectedFile}
                fullWidth
                sx={{ py: 1.5, fontWeight: 'bold' }}
            >
                {isLoading ? <Loading color="inherit" size={24} /> : 'Register My Face'}
            </Button>
             <RaButton 
                label="Back to My Lessons" 
                onClick={() => window.history.back()} // Or use react-router Link if more appropriate
                sx={{mt: 2, display: 'block', mx: 'auto'}} // Center the button
                variant="text" // Less prominent than the main action
            />
        </Paper>
    );
};