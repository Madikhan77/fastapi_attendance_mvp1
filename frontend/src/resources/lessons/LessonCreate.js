import * as React from "react";
import { Create, SimpleForm, TextInput } from 'react-admin';

// Add required validator
const required = (message = 'Required') => value => value ? undefined : message;

export const LessonCreate = (props) => (
    <Create {...props} title="Create Lesson">
        <SimpleForm sx={{ p: 2 }}> {/* Added padding to the form container */}
            <TextInput source="title" validate={required()} fullWidth sx={{ mb: 2 }} /> {/* Added fullWidth and bottom margin */}
            <TextInput source="description" multiline fullWidth sx={{ mb: 2 }} /> {/* Added fullWidth and bottom margin */}
        </SimpleForm>
    </Create>
);
