#ifndef MEMBRANE_H
#define MEMBRANE_H
#include <string>
#include <iostream>
#include <fstream>
#include <vector>
#include <math.h>
#include "General_functions.hpp"

using namespace std;

class Membrane
{
    
public: //these are using in monte carlo flip function. for defining them as private variables, we have tow ways: defining monte_carlo_flip as a member of this class or writing some functions to make them accessible out of membrane class.
    
    double Membrane_Node_Mass=1.0;//  also use in MD loop and should not be private unless we write some functions to get it outside the class
    double Total_Potential_Energy;
    
    
    int membrane_counter;
    int Membrane_num_of_Node_Pairs; //??? (This variable should be defined and explained)
    int Membrane_num_of_Triangle_Pairs;
    
    
    string output_file_neme;
    
    
    vector<vector<double> >Membrane_Node_Position;
    vector<vector<int> > Membrane_triangle_list;
    vector<vector<int> > membrane_triangle_pair_list;
    //vector<vector<int> > Membrane_Node_Pair_list;
	vector<vector<int> > Membrane_Edges;// this variable is  the same as Membrane_Node_pair_list. I think  the name "Membrane_Edges" is less confusing. and also we fill it in a different way.
    vector<vector<int> > Membrane_Triangle_Pair_Nodes;
	vector<vector<double> > Membrane_Node_Velocity;// also update in MD loop and should not be private unless we write some functions to get it outside the class
    vector<vector<double> > Membrane_Node_Force;// also update in MD loop and should not be private unless we write some functions to get it outside the class
    vector<vector<int> > node_neighbour_list;
    
    
	void Membrane_Triangle_Pair_and_Edges_Identifier(); //I guess this will use in MD loop and thus it should define as a public membere of class.
	//int Membrane_num_of_Node_Pair_Counter();// Hoda: no need to this function after modifying Membrane_Triangle_Pair_and_Edges_Identifier
	//void Membrane_num_of_Node_Pair_Counter_2();//Hoda: no need to this function after modifying Membrane_Triangle_Pair_and_Edges_Identifier
	void Elastic_Force_Calculator();
	void Membrane_MD_Evolution ();
	void ConstantSurfaceForceLocalTriangles ();
    void node_neighbour_list_constructor();
    
private:
    
    int Membrane_num_of_Nodes;
    /*constants*/
    //This is the number of nodes on the membrane (Both the outer membrane and the Nucleus). This is the first number that appears in the 'membrane' file (once opend with a text editor)
    int Membrane_num_of_Triangles; //This is the number of triangles on the membrane (Both the outer membrane and the Nucleus). This is the number that appears in the 'membrane' file after the node position list is finished and before Gmesh lists the nodes that make a triangle.
    int **Membrane_Normal_direction; //??? (These 2 elements should be defined and explained)
    
    
    double Total_Kinetic_Energy;
    double Membrane_total_potential_Energy=0.0;
    double Membrane_spring_coefficient=5.0; // streching constant
    double Membrane_bending_coefficient=30.0; // bending constant
    double Membrane_damping_coefficient=0.01; // Viscosity of the Mmmbrane. It is applied in Force calculation for the Membrane Node pairs. I have commented out these parts in the 'Membrane_Force_Calculator' because I think the current code does not need it (some energy consuming array calculations were invloved).
    double K_surfaceConstant_local=100.0;
    double Membrane_spring_force_cutt_off=10000.0;
    double membraneshiftinXdirection=0.0; //???
    double membraneshiftinZdirection=0.0; //???
    double Membrane_downward_speed=0.0; //???
    //bool =0;
	double com[3]; //center of mass
    double Min_node_pair_length, Max_node_pair_length, Average_node_pair_length;
    
    
	
    bool on_or_off_Membrane_spring_force_cutt_off=0; //??? I add it myself because virus should not have cut off
    
    
    
    /*variables*/
    
    
    
    
    double Average_Membrane_Node_Distance();
    void read_gmesh_file (string gmesh_file);
    void read_membrabe_input(string input_file);
	void Membrane_triangle_pair_counter ();
    void Membrane_Normal_direction_Identifier();
    void Membrane_Normal_direction_Identifier(double x, double y, double z);
	
    void Membrane_potential_1 (void);
    void Membrane_potential_2 (void);
    void membrane_node_pair_identifier(void);
    void membrane_triangle_pair_identifier(void);
    void Membrane_bending_potetial(void);
    void check(void);
    
public:
    
    Membrane(string input_file_name , string membrane_mesh_file_name)
    {
        read_membrabe_input(input_file_name);
        read_gmesh_file(membrane_mesh_file_name);
        output_file_neme=membrane_mesh_file_name ;// it is for generating trajectory file. it can be modifyed to have date and time in it.this modification can be done in main.
        cout<<"Membrane class initiated"<<endl;
        Membrane_Normal_direction_Identifier();
		Membrane_triangle_pair_counter();
		if (Membrane_num_of_Triangle_Pairs != 3*(Membrane_triangle_list.size())/2)
		{cout<<"error! some triangles have less or more neighbour than 3"<<endl;}
		Membrane_Triangle_Pair_and_Edges_Identifier();
        
        
        
    }
    
    Membrane(string membrane_mesh_file_name)
    {
        read_gmesh_file(membrane_mesh_file_name);
        output_file_neme=membrane_mesh_file_name;
        cout<<"Membrane class initiated"<<endl;
		Membrane_Normal_direction_Identifier();
		Membrane_triangle_pair_counter();
		if (Membrane_num_of_Triangle_Pairs != 3*(Membrane_triangle_list.size())/2)
		{cout<<"error! some triangles have less or more neighbour than 3"<<endl;}
		Membrane_Triangle_Pair_and_Edges_Identifier();
		cout<< "Average node distance is   "<<Average_Membrane_Node_Distance()<<endl;
	}
    
    Membrane(string membrane_mesh_file_name, double x, double y, double z)
    {
        read_gmesh_file(membrane_mesh_file_name);
        output_file_neme=membrane_mesh_file_name;
        cout<<"\n\nNumber of Nodes="<<Membrane_num_of_Nodes<<endl;
        cout<<"Number of triangles="<<Membrane_num_of_Triangles<<endl;
        Membrane_Normal_direction_Identifier(x, y, z);
        Membrane_triangle_pair_counter();
        cout<<"Number of triangle pairs="<<Membrane_num_of_Triangle_Pairs<<endl;
        if (Membrane_num_of_Triangle_Pairs != 3*(Membrane_triangle_list.size())/2){
            cout<<"Warning! some triangles have less or more neighbour than 3"<<endl;
            
        }
//        Membrane_Triangle_Pair_and_Edges_Identifier();
        membrane_node_pair_identifier();
        node_neighbour_list_constructor();
        membrane_triangle_pair_identifier();
        check();
        cout<<"Membrane class initiated.\n";
//        cout<< "Average node distance is   "<<Average_Membrane_Node_Distance()<<endl;
    }
    
    
    
    int return_num_of_nodes(void){
        return Membrane_num_of_Nodes;
    }
    void shift_position (double x, double y, double z){
        for (int i=0; i<Membrane_num_of_Nodes; i++) {
            Membrane_Node_Position[i][0]+=x;
            Membrane_Node_Position[i][1]+=y;
            Membrane_Node_Position[i][2]+=z;
        }
    }
    void shift_velocity (double vx, double vy, double vz){
        for (int i=0; i<Membrane_num_of_Nodes; i++) {
            Membrane_Node_Velocity[i][0]+=vx;
            Membrane_Node_Velocity[i][1]+=vy;
            Membrane_Node_Velocity[i][2]+=vz;
        }
    }
    int return_membrane_num_of_triangle(){
        return Membrane_num_of_Triangles;
    }
    void calculate_average_force(void){
        double average_force_x=0, average_force_y=0, average_force_z=0;
        for(int j=0 ; j<Membrane_num_of_Nodes ; j++){
            average_force_x+=Membrane_Node_Force[j][0];
            average_force_y+=Membrane_Node_Force[j][1];
            average_force_z+=Membrane_Node_Force[j][2];
            
        }
        cout<<"\n\naverage_force_x="<<average_force_x/Membrane_num_of_Nodes<<"\naverage_force_y="<<average_force_y/Membrane_num_of_Nodes<<"\naverage_force_z="<<average_force_z/Membrane_num_of_Nodes<<endl;
    }
};

#endif // MEMBRANE_H
