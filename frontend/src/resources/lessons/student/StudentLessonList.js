import * as React from 'react';
import { useDataProvider, Loading, Error as RaError } from 'react-admin';
import { Link } from 'react-router-dom';
import { List, ListItem, ListItemText, Typography, Paper, Box } from '@mui/material'; // Added Box
// For ListItemButton if needed, but using Link component on ListItem handles it
// import ListItemButton from '@mui/material/ListItemButton';

export const StudentLessonList = () => {
    const dataProvider = useDataProvider(); // dataProvider is fetched but not used in this snippet due to direct fetch
    const [lessons, setLessons] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState();

    React.useEffect(() => {
        const fetchLessons = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/student/lessons`, {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch lessons' }));
                    throw new Error(errorData.detail || 'Failed to fetch lessons');
                }
                const data = await response.json();
                setLessons(data);
            } catch (e) {
                setError(e);
            } finally {
                setLoading(false);
            }
        };
        fetchLessons();
    }, [dataProvider]); // dataProvider in dependency array though not directly used in fetch

    if (loading) return <Loading />;
    if (error) return <RaError title="Error fetching lessons" error={{ message: error.message }} />;
    if (!lessons || lessons.length === 0) {
        return (
            <Paper sx={{ p: 3, textAlign: 'center', mt: 2, maxWidth: 600, mx: 'auto' }}> {/* Centered and max width */}
                <Typography variant="h5" component="h2" gutterBottom sx={{ mb: 2 }}>My Enrolled Lessons</Typography>
                <Typography>You are not currently enrolled in any lessons.</Typography>
            </Paper>
        );
    }

    return (
        <Box sx={{ p: 2, maxWidth: 800, mx: 'auto' }}> {/* Added Box for centering and max width */}
            <Typography variant="h4" component="h1" gutterBottom sx={{ textAlign: 'center', mb: 3 }}>
                My Enrolled Lessons
            </Typography>
            <List>
                {lessons.map(lesson => (
                    <Paper key={lesson.id} elevation={2} sx={{ mb: 2 }}> {/* Wrap ListItem in Paper for better separation */}
                        <ListItem 
                            component={Link} 
                            to={`/student/lessons/${lesson.id}`}
                            sx={{ 
                                py: 2, // Padding top and bottom
                                '&:hover': {
                                    backgroundColor: 'action.hover',
                                    boxShadow: 3, // Add shadow on hover
                                },
                                borderRadius: 1, // Rounded corners for the list item itself
                            }}
                        >
                            <ListItemText 
                                primary={lesson.title} 
                                secondary={lesson.description} 
                                primaryTypographyProps={{ variant: 'h6', component: 'div', color: 'primary.main' }}
                                secondaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
                            />
                        </ListItem>
                    </Paper>
                ))}
            </List>
        </Box>
    );
};
