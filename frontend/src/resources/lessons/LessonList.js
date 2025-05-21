import * as React from "react";
import { List, Datagrid, TextField, DateField, EditButton, DeleteButton } from 'react-admin';

export const LessonList = (props) => (
    <List {...props} title="My Lessons">
        <Datagrid rowClick="edit">
            <TextField source="id" />
            <TextField source="title" />
            <TextField source="description" />
            <DateField source="created_at" label="Created At" showTime />
            <EditButton />
            <DeleteButton />
        </Datagrid>
    </List>
);
