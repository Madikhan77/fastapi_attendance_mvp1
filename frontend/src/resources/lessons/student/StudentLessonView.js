import * as React from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import { useDataProvider, Loading, Error as RaError, useNotify, Button as RaButton } from 'react-admin';
import { Typography, Paper, List, ListItem, ListItemText, Button, Divider, Box, Input } from '@mui/material'; // Added Input

export const StudentLessonView = () => {
    const { lessonId } = useParams();
    const dataProvider = useDataProvider(); // dataProvider is fetched but not used in this snippet due to direct fetch
    const notify = useNotify();
    const [lesson, setLesson] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState();
    const [selectedFile, setSelectedFile] = React.useState(null);
    const [isAttendanceLoading, setIsAttendanceLoading] = React.useState(false);
    const [attendanceServerMessage, setAttendanceServerMessage] = React.useState('');
    const [attendanceServerMessageType, setAttendanceServerMessageType] = React.useState('info');


    React.useEffect(() => {
        const fetchLessonDetails = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/lessons/${lessonId}`, {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch lesson details' }));
                    throw new Error(errorData.detail || 'Failed to fetch lesson details');
                }
                const data = await response.json();
                setLesson(data);
            } catch (e) {
                setError(e);
            } finally {
                setLoading(false);
            }
        };
        fetchLessonDetails();
    }, [dataProvider, lessonId]); // dataProvider in dependency array

    const handleFileChange = (event) => {
        setSelectedFile(event.target.files[0]);
        setAttendanceServerMessage(''); // Clear previous messages on new file selection
    };

    const handleMarkAttendance = async () => {
        if (!selectedFile) {
            notify('Please select a file to simulate camera capture.', { type: 'warning' });
            setAttendanceServerMessage('Please select an image file to mark attendance.');
            setAttendanceServerMessageType('warning');
            return;
        }
        
        setIsAttendanceLoading(true);
        setAttendanceServerMessage('');

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/attendance/${lessonId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });

            const responseData = await response.json();

            if (!response.ok) {
                const errorMessage = responseData.detail || `HTTP error! Status: ${response.status}`;
                throw new Error(errorMessage);
            }
            
            const successMessage = `Attendance confirmed! Similarity: ${responseData.similarity.toFixed(4)}`;
            notify(successMessage, { type: 'success' });
            setAttendanceServerMessage(successMessage);
            setAttendanceServerMessageType('success');
            setSelectedFile(null); 
            const fileInput = document.getElementById('attendance-image-input'); 
            if (fileInput) fileInput.value = '';

        } catch (error) {
            console.error('Attendance marking error:', error);
            const userFriendlyErrorMessage = error.message || 'An unknown error occurred.';
            notify(`Attendance Error: ${userFriendlyErrorMessage}`, { type: 'error' });
            setAttendanceServerMessage(userFriendlyErrorMessage);
            setAttendanceServerMessageType('error');
        } finally {
            setIsAttendanceLoading(false);
        }
    };

    if (loading) return <Loading />;
    if (error) return <RaError title="Error fetching lesson" error={{ message: error.message }} />;
    if (!lesson) return (
        <Paper sx={{p:3, textAlign: 'center', mt: 2, maxWidth: 600, mx: 'auto' }}>
            <Typography variant="h5" component="h2" gutterBottom>Lesson Not Found</Typography>
            <Typography sx={{ mb: 2 }}>The lesson you are looking for does not exist or you may not have access.</Typography>
            <RaButton label="Back to My Lessons" component={RouterLink} to="/student/lessons" variant="outlined" />
        </Paper>
    );

    return (
        <Box sx={{ p: 2, maxWidth: 900, mx: 'auto' }}>
            <Paper sx={{ p: 3, mb: 3, overflow: 'hidden' }}> {/* Added overflow hidden for safety with negative margins */}
                <Typography variant="h4" component="h1" gutterBottom sx={{ mb: 1 }}>{lesson.title}</Typography>
                <Typography variant="body1" paragraph sx={{ color: 'text.secondary', mb: 2 }}>
                    {lesson.description || "No description available."}
                </Typography>
            </Paper>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" component="h2" gutterBottom sx={{ mb: 2 }}>Lesson Files</Typography>
                {lesson.files && lesson.files.length > 0 ? (
                    <List disablePadding>
                        {lesson.files.map(file => (
                            <ListItem 
                                key={file.id} 
                                button // MUI ListItem with `button` prop or using `ListItemButton` is fine
                                component="a" 
                                href={`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/files/${file.id}/download?token=${localStorage.getItem('token')}`} 
                                target="_blank"
                                rel="noopener noreferrer"
                                sx={{ 
                                    mb: 1, 
                                    border: '1px solid #ddd',
                                    borderRadius: 1, // Using theme's border radius
                                    '&:hover': { 
                                        backgroundColor: 'action.hover',
                                        boxShadow: 1,
                                    },
                                    py: 1.5, px: 2 // Padding
                                }}
                            >
                                <ListItemText primary={file.filename} primaryTypographyProps={{ fontWeight: 'medium', color: 'primary.main' }} />
                            </ListItem>
                        ))}
                    </List>
                ) : <Typography sx={{ color: 'text.secondary', fontStyle: 'italic' }}>No files available for this lesson.</Typography>}
            </Paper>
            
            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" component="h2" gutterBottom sx={{ mb: 2 }}>Mark Attendance</Typography>
                
                {attendanceServerMessage && (
                    <Alert severity={attendanceServerMessageType} sx={{ mb: 2, '.MuiAlert-message': { width: '100%' } }}>
                        {attendanceServerMessage}
                    </Alert>
                )}

                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 1.5 }}>
                    <Input
                        type="file"
                        onChange={handleFileChange}
                        id="attendance-image-input" // Ensure ID matches logic for clearing
                        sx={{ display: 'none' }} 
                        inputProps={{ accept:"image/*" }}
                    />
                    <label htmlFor="attendance-image-input">
                        <Button variant="outlined" component="span">
                            Choose Image
                        </Button>
                    </label>
                    {selectedFile && <Typography variant="body2" sx={{ml:0.5, mt:0.5, fontStyle: 'italic'}}>{selectedFile.name}</Typography>}
                    <Button 
                        variant="contained" 
                        onClick={handleMarkAttendance} 
                        disabled={isAttendanceLoading || !selectedFile} 
                        sx={{ mt: 1 }} 
                    >
                        {isAttendanceLoading ? <Loading color="inherit" size={24}/> : 'Simulate Camera Capture & Mark Attendance'}
                    </Button>
                </Box>
            </Paper>

            <Box sx={{ textAlign: 'center', mt: 3, mb:2 }}>
                <RaButton label="Back to My Lessons" component={RouterLink} to="/student/lessons" variant="contained" size="large"/>
            </Box>
        </Box>
    );
};
