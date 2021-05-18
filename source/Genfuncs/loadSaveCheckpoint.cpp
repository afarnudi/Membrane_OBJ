//
//  General_functions.cpp
//  Cell-Durotaxis
//
//  Created by Ali Farnudi on 27/08/2017.
//  Copyright © 2017 Ali Farnudi. All rights reserved.
//
#include <iostream>
#include <fstream>
#include "General_constants.h"
#include "OpenMM_structs.h"
#include <boost/filesystem.hpp>

using namespace std;

void loadCheckpoint(MyOpenMMData* omm){
    cout<<"Loading checkpoint from: "<<generalParameters.Checkpoint_path<<endl;
    try {
        std::filebuf rfb;
        rfb.open (generalParameters.Checkpoint_path.c_str(),std::ios::in);
        std::istream rcheckpoint(&rfb);
        omm->context->loadCheckpoint(rcheckpoint);
    } catch (const std::exception& e) {
        try {
            generalParameters.usingBackupCheckpoint=true;
            std::filebuf rfb;
            string backupcheckpoint = generalParameters.Checkpoint_path + "Backup";
            rfb.open (backupcheckpoint.c_str(),std::ios::in);
            std::istream rcheckpoint(&rfb);
            omm->context->loadCheckpoint(rcheckpoint);
        } catch (const std::exception& e) {
            string errorMessage = TWARN;
            errorMessage+="Loading Checkpoint: Both the checkpoint and the backup are curropt. This simulation cannot be resumed.\n";
            errorMessage+= TRESET;
            throw std::runtime_error(errorMessage);
        }
    }
}



void saveCheckpoint(MyOpenMMData* omm, string ckeckpoint_name){
    string ckeckpoint_name_backup = ckeckpoint_name + "Backup";
    if (!generalParameters.usingBackupCheckpoint) {
        boost::filesystem::copy_file(ckeckpoint_name, ckeckpoint_name_backup, boost::filesystem::copy_option::overwrite_if_exists);
    } else {
        generalParameters.usingBackupCheckpoint = false;
    }
    
        
    
    std::filebuf wfb;
    wfb.open (ckeckpoint_name.c_str(),std::ios::out);
    std::ostream wcheckpoint(&wfb);
    omm->context->createCheckpoint(wcheckpoint);
    wfb.close();
}