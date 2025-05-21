import * as React from 'react';
import {
    Edit, SimpleForm, TextInput, ReferenceManyField, Datagrid, TextField,
    FileField, CreateButton, ReferenceInput, SelectInput, FunctionField, Button,
    useNotify, useRefresh, useRecordContext, useDataProvider, DeleteButton,
    TopToolbar, ShowButton, ListButton
} from 'react-admin';
import { Box, Paper, Typography, Divider, Input } from '@mui/material'; // Moved import statement here

// Add required validator
const required = (message = 'Required') => value => value ? undefined : message;

const LessonEditActions = () => (
    <TopToolbar>
        <ShowButton />
        <ListButton />
    </TopToolbar>
);

// Custom File Upload Component within LessonEdit
const LessonFileUpload = () => {
    const record = useRecordContext();
    const notify = useNotify();
    const refresh = useRefresh();
    const [file, setFile] = React.useState();
    const [fileName, setFileName] = React.useState('');

    const handleFileChange = (e) => {
        const currentFile = e.target.files[0];
        if (currentFile) {
            setFile(currentFile);
            setFileName(currentFile.name);
        } else {
            setFile(null);
            setFileName('');
        }
    };

    const handleFileUpload = async () => {
        if (!file || !record) return;
        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            if (!token) {
                notify('Authentication token not found. Please log in.', { type: 'warning' });
                return;
            }
            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/lessons/${record.id}/files`, {
                method: 'POST',
                body: formData,
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'File upload failed' }));
                throw new Error(errorData.detail || 'File upload failed');
            }
            notify('File uploaded successfully');
            refresh();
            setFile(null);
            setFileName('');
            if(document.getElementById('file-upload-input-styled')) {
                 document.getElementById('file-upload-input-styled').value = ''; // Reset file input
            }
        } catch (error) {
            notify(`Error: ${error.message || 'File upload failed'}`, { type: 'warning' });
        }
    };

    return (
        <Box sx={{ mt: 2, mb: 2, p: 2, border: '1px dashed grey', borderRadius: '4px' }}>
            <Typography variant="h6" gutterBottom>Upload New File</Typography>
            <Input
                type="file"
                onChange={handleFileChange}
                id="file-upload-input-styled" // Changed id to avoid conflict if original is still somewhere
                sx={{ display: 'none' }} // Hide the default input
            />
            <label htmlFor="file-upload-input-styled">
                <Button component="span" variant="outlined" sx={{ mr: 1 }}>
                    Choose File
                </Button>
            </label>
            {fileName && <Typography component="span" sx={{ mr: 1 }}>{fileName}</Typography>}
            <Button label="Upload File" onClick={handleFileUpload} disabled={!file} variant="contained" />
        </Box>
    );
};


const EnrollStudentForm = () => {
    const record = useRecordContext();
    const notify = useNotify();
    const refresh = useRefresh();
    const [studentId, setStudentId] = React.useState('');

    const handleEnroll = async () => {
        if (!studentId || !record) return;
        try {
            const token = localStorage.getItem('token');
            if (!token) {
                notify('Authentication token not found. Please log in.', { type: 'warning' });
                return;
            }
            const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/lessons/${record.id}/enroll`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ user_id: parseInt(studentId), lesson_id: record.id })
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Enrollment failed' }));
                throw new Error(errorData.detail || 'Enrollment failed');
            }
            notify('Student enrolled successfully');
            refresh();
            setStudentId('');
        } catch (error) {
            notify(`Error: ${error.message || 'Enrollment failed'}`, { type: 'warning' });
        }
    };

    return (
        <Box sx={{ mt: 2, mb: 2, p: 2, border: '1px dashed grey', borderRadius: '4px' }}>
            <Typography variant="h6" gutterBottom>Enroll New Student</Typography>
            <ReferenceInput label="Select Student" source="user_id_to_enroll" reference="users" filter={{ role: 'student' }} perPage={1000} sx={{ width: '100%', mb:1 }}>
                <SelectInput optionText="username" onChange={(event) => setStudentId(event.target.value)} helperText={false} fullWidth />
            </ReferenceInput>
            <Button label="Enroll Student" onClick={handleEnroll} disabled={!studentId} variant="contained" />
        </Box>
    );
};


export const LessonEdit = (props) => {
    // notify and refresh are not directly used here anymore, but CustomFileDeleteButton uses them.
    // This is fine as hooks are called within CustomFileDeleteButton.

    return (
        <Edit {...props} title="Edit Lesson" actions={<LessonEditActions />}>
            <SimpleForm sx={{ p: 2 }}> {/* Added padding to the main form container */}
                <Typography variant="h5" gutterBottom>Lesson Details</Typography>
                <Paper sx={{ p: 2, mb: 3 }}> {/* Paper for basic info section */}
                    <TextInput source="id" disabled fullWidth sx={{ mb: 2 }} />
                    <TextInput source="title" validate={required()} fullWidth sx={{ mb: 2 }} />
                    <TextInput source="description" multiline fullWidth sx={{ mb: 2 }} />
                </Paper>
                
                <Divider sx={{ my: 3 }} />

                <Typography variant="h5" gutterBottom>Lesson Files</Typography>
                <Paper sx={{ p: 2, mb: 3 }}> {/* Paper for files section */}
                    <ReferenceManyField label="Current Files" reference="lessonfiles" target="lesson_id" perPage={10}>
                        <Datagrid bulkActionButtons={false} sx={{ '& .RaDatagrid-headerCell': { fontWeight: 'bold' } }}>
                            <TextField source="id" label="ID" />
                            <TextField source="filename" />
                            <FunctionField label="Download" render={record => (
                                <Button
                                    label="Download"
                                    onClick={() => {
                                        const token = localStorage.getItem('token');
                                        // notify is not available here directly unless passed or CustomFileDeleteButton's notify is used
                                        if (!token) {
                                            // Consider using a shared context for notify or pass it down if needed outside hooks
                                            console.warn('Authentication token not found. Please log in.');
                                            return;
                                        }
                                        window.open(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/files/${record.id}/download?token=${token}`, '_blank');
                                    }}
                                    variant="outlined" // Consistent button styling
                                    size="small"
                                />
                            )} />
                            <FunctionField label="Actions" render={fileRecord => {
                                const CustomFileDeleteButton = ({ record }) => {
                                    const notify = useNotify(); // Hooks are fine here as this is a component
                                    const refresh = useRefresh();
                                    const handleDelete = async () => {
                                        if (window.confirm('Are you sure you want to delete this file?')) {
                                            try {
                                                const token = localStorage.getItem('token');
                                                if (!token) {
                                                    notify('Authentication token not found. Please log in.', { type: 'warning' });
                                                    return;
                                                }
                                                const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/files/${record.id}`, {
                                                    method: 'DELETE',
                                                    headers: { 'Authorization': `Bearer ${token}` },
                                                });
                                                if (!response.ok) {
                                                    const errorText = await response.text();
                                                    throw new Error(`Failed to delete file. Status: ${response.status}, Message: ${errorText}`);
                                                }
                                                notify('File deleted successfully', { type: 'info' });
                                                refresh();
                                            } catch (error) {
                                                notify(`Error: ${error.message || 'Deletion failed'}`, { type: 'warning' });
                                            }
                                        }
                                    };
                                    return <Button label="Delete File" onClick={handleDelete} color="error" variant="outlined" size="small" />;
                                };
                                return <CustomFileDeleteButton record={fileRecord} />;
                            }} />
                        </Datagrid>
                    </ReferenceManyField>
                    <LessonFileUpload /> {/* Custom component already includes Box and Typography */}
                </Paper>

                <Divider sx={{ my: 3 }} />

                <Typography variant="h5" gutterBottom>Student Enrollments</Typography>
                <Paper sx={{ p: 2, mb: 3 }}> {/* Paper for enrollments section */}
                    <ReferenceManyField label="Currently Enrolled" reference="studentlessonenrollments" target="lesson_id" perPage={10}>
                         <Datagrid bulkActionButtons={false} sx={{ '& .RaDatagrid-headerCell': { fontWeight: 'bold' } }}>
                            <TextField source="student.username" label="Username" />
                            <TextField source="student.role" label="Role" />
                            <FunctionField label="Actions" render={enrollmentRecord => {
                                const currentLesson = props.record || useRecordContext(); // Ensure currentLesson is available
                                const notify = useNotify(); // Hooks are fine here
                                const refresh = useRefresh();

                                return (
                                <Button
                                    label="Unenroll"
                                    onClick={async () => {
                                        if (!currentLesson || !currentLesson.id) {
                                            notify('Lesson context not found.', { type: 'warning' });
                                            return;
                                        }
                                        if(window.confirm(`Are you sure you want to unenroll student ID ${enrollmentRecord.user_id}?`)) {
                                            try {
                                                const token = localStorage.getItem('token');
                                                if (!token) {
                                                    notify('Authentication token not found. Please log in.', { type: 'warning' });
                                                    return;
                                                }
                                                const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/lessons/${currentLesson.id}/unenroll`, {
                                                    method: 'DELETE',
                                                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                                                    body: JSON.stringify({ user_id: enrollmentRecord.user_id, lesson_id: currentLesson.id })
                                                });
                                                if (!response.ok) {
                                                    const errorData = await response.json().catch(() => ({detail: 'Unenrollment failed'}));
                                                    throw new Error(errorData.detail || 'Unenrollment failed');
                                                }
                                                notify('Student unenrolled successfully');
                                                refresh();
                                            } catch (error) {
                                                notify(`Error: ${error.message || 'Unenrollment failed'}`, { type: 'warning' });
                                            }
                                        }
                                    }}
                                    color="error" // For destructive action
                                    variant="outlined" // Consistent button styling
                                    size="small"
                                />
                            )}} />
                        </Datagrid>
                    </ReferenceManyField>
                    <EnrollStudentForm /> {/* Custom component already includes Box and Typography */}
                </Paper>
            </SimpleForm>
        </Edit>
    );

}